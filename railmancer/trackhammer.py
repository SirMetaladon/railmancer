import random, math, time
from railmancer import tools, track, lines, vmfpy
from railmancer import cfg as TEST
from scipy.spatial import distance
import numpy as np

# This is an algoritm for pathing a mainline through the playable area without bumping into itself. Last part pending.

debug_overall_count: int = 0
logLength: float = 0


# From a list, pick random entries and transfer them to a second list until you either hit count or run out.
def sprinkle_selector(list, count):

    import random

    output = []
    working = list[:]
    for _ in range(count):
        choice = random.choice(working)
        working.remove(choice)
        output += [choice]
        if count == len(output) or len(working) == 0:
            break

    return output


# From a set of real coordinates, get a block ID in exclusion block space and return a list of the nearest 2x2 of blocks in a list
def get_block_ids(point):

    x, y, z = point

    fx = x / BlockHorizontal
    fy = y / BlockHorizontal
    fz = z / BlockVertical

    bx = math.floor(fx)
    by = math.floor(fy)
    bz = math.floor(fz)

    # Decide which side of the block center we're on
    xs = [bx, bx + 1] if fx - bx > 0.5 else [bx - 1, bx]
    ys = [by, by + 1] if fy - by > 0.5 else [by - 1, by]
    zs = [bz, bz + 1] if fz - bz > 0.5 else [bz - 1, bz]

    return [f"{x},{y},{z}" for x in xs for y in ys for z in zs]


# From a list of points, find all blocks that are NOT already spoken for and reserve them, returning a list of valid newly reserved blocks.
def blocks_new(list_of_points):

    new_blocks = []

    for point in list_of_points:
        block_ids = get_block_ids(point)

        for block in block_ids:
            if block not in Blocks:
                new_blocks += [block]
                Blocks[block] = True

    return new_blocks


# Patch function that takes all the imported points and prefills the Blocking system with them, ensuring future Trackhammers do not intersect with existing track.
def exclude_existing():

    current_points = lines.get_all_track_points()
    new_blocks = blocks_new(current_points)
    print(f"Imported {len(current_points)} points, created {len(new_blocks)} Blocks.")


# For this specific point, does the 2x2 of closest blocks contain any reserved blocks? If so, this space is not legal.
def are_points_blocked(list_of_points):

    for point in list_of_points:
        block_ids = get_block_ids(point)
        for block in block_ids:
            if block in Blocks:
                return True

    return False


# For a list of string block ID's, remove them from the currently reserved list of blocks
def blocks_remove(list_of_block_ids):

    global Blocks

    for entry in list_of_block_ids:
        if entry in Blocks:
            Blocks.pop(entry)


# From a pair of track nodes reprensenting a piece of rail, guess at the intermediate shape and return a short list of points to check with the block occlusion algorithm.
def get_block_points_from_nodes(current_node, next_node):

    extras = []
    cutoff = BlockHorizontal * 0.85  # horizontal block dist
    dist = distance.euclidean(current_node[0], next_node[0])
    iterations = math.floor(dist / cutoff)

    start = np.asarray(current_node[0])
    end = np.asarray(next_node[0])

    if iterations > 1:
        for iter in range(1, iterations):
            extras += [tools.linterp(start, end, iter / (iterations + 1))]

    return [next_node[0]] + extras


# From a model and a current node, return the resulting node, and whether the track is valid according to blocking and maximum border size.
def generate_pieces_from_node_and_mdl(model, prev_node, mode):

    current_node = track.get_new_node_from_node_and_model(
        model, prev_node, False, 512, 0
    )

    points = get_block_points_from_nodes(
        prev_node,
        current_node,
    )

    end = (
        int(current_node[0][0]),
        int(current_node[0][1]),
    )

    if not tools.within2d(end, TEST.get("trackhammer_border")):
        return None

    if are_points_blocked(points):
        return None

    def add_model(shift=(0, 0, 0), mdloverwrite=""):

        mdl = mdloverwrite if mdloverwrite != "" else model

        pos, yaw = track.convert_model_nodes_to_real_pos_and_angle(
            mdl,
            prev_node,
            current_node,
            shift,
        )

        return (model, pos, yaw)

    heading = prev_node[2]
    end_direction = current_node[1]

    if mode == "left":

        shifts = {
            "0fw": ((0, 0, 0), (0, -192, 0)),
            "1lt": ((-48, 0, 0), (0, -192, 0)),
            "2lt": ((-96, 0, 0), (0, -192, 0)),
            "4lt": ((-64, 0, 0), (0, -192, 0)),
            "1rt": ((0, 0, 0), (-48, -192, 0)),
            "2rt": ((0, 0, 0), (-96, -192, 0)),
            "4rt": ((0, 0, 0), (-64, -192, 0)),
        }

        if "8lt" in model:
            main_shift = (-128, 0, 0)
            siding_shift = (0, -192, 0)

        elif "8rt" in model:
            main_shift = (0, 0, 0)
            siding_shift = (-128, -192, 0)

        else:
            main_shift, siding_shift = shifts[end_direction]

    else:

        main_shift = (0, 0, 0)
        siding_shift = (0, -192, 0)

    models = [add_model(tools.rot_orth(main_shift, heading))]

    if mode == "left":
        models += [add_model(tools.rot_orth(siding_shift, heading))]

    median_extra_length = 0
    track_length = track.get_length(model) + median_extra_length

    return (
        current_node,
        points,
        models,
        track_length,
    )


# Queries the track system to find valid tracks according to grade and curvature rules, then returns a randomized selection
def generate_selection_of_possible_tracks(node, count, params={}):

    # takes direction, minumum radius level, minimum grade level, maximum grade level
    possible_tracks = track.valid_next_tracks(node[1], params)
    options = sprinkle_selector(possible_tracks, count)

    if len(options) == 0:
        print("Failed to find selection: ", node, count, params)

    return options


def display_blocks_in_vmf():

    # Converts a block to coordinates to create brushes with
    def block_id_to_coords(block_id):

        coords = block_id.split(",")
        x = int(coords[0])
        y = int(coords[1])
        z = int(coords[2])

        return x * BlockHorizontal, y * BlockHorizontal, z * BlockVertical

    # For debugging purposes - creates brushes that demonstrate where the block boundaries are
    for block in Blocks:

        x, y, z = block_id_to_coords(block)

        vmfpy.add_brush(
            [
                x,
                x + BlockHorizontal,
                y,
                y + BlockHorizontal,
                z,
                z + BlockVertical,
                "dev/dev_measurewall01d",
                0,
                0,
                "24",
            ]
        )

    print(f"Added {len(Blocks)} pathfinding blocks.")


# From the block queue, push up to the block that corresponds with the standoff length, forward or backward, then return the current step
def update_blocks(current_steps, blocks_step):

    current_length = current_steps[-1]["length"]

    if blocks_step >= len(current_steps):

        print("This should not be possible!")
        return blocks_step

    else:

        distance_away = current_length - current_steps[blocks_step]["length"]
        direction_to_go = (
            "Forward" if distance_away > Block_Standoff_Distance else "Backward"
        )

    step_to_test = blocks_step

    if direction_to_go == "Forward":
        while (
            current_length - current_steps[step_to_test + 1]["length"]
        ) > Block_Standoff_Distance:

            blocks_added = blocks_new(current_steps[step_to_test]["points"])

            existing_blocks = current_steps[step_to_test].get("blocks_added", [])
            current_steps[step_to_test]["blocks_added"] = existing_blocks + blocks_added
            step_to_test += 1

    if direction_to_go == "Backward":
        while (
            current_length - current_steps[step_to_test - 1]["length"]
        ) <= Block_Standoff_Distance and step_to_test > 0:

            blocks_remove(current_steps[step_to_test]["blocks_added"])

            current_steps[step_to_test]["blocks_added"] = []
            step_to_test -= 1

    return step_to_test


# Initializes the Trackhammer with relevant global fields.
def initialize():

    global BlockHorizontal
    global BlockVertical
    global Block_Standoff_Distance

    BlockHorizontal = TEST.get("trackhammer_block_size_horizontal")
    BlockVertical = TEST.get("sector_minimum_height") * 1.05
    Block_Standoff_Distance = TEST.get("trackhammer_block_standoff_distance")

    global Blocks
    Blocks = {}


def generation_process(
    start_node,
    track_profile,
    backtrack_distance,
    candidates_to_generate,
    params,
):

    print("Started permutation: ", backtrack_distance, candidates_to_generate)

    global debug_overall_count, logLength

    blocks_current_step_index = 0

    longest_fail = []
    longest_fail_length = 0

    debug_reporting_interval = 10000
    debug_maximum_count = debug_reporting_interval * 25

    def debug_logger(steps, new_length):

        global logLength
        global debug_overall_count

        if debug_overall_count % debug_reporting_interval == 0:
            logLength = max(logLength, round(tools.miles(new_length), 3))
            print()
            print(
                f"{len(steps[0]["candidate_tracks"])} base candidates,"
                f"{len(steps)} current steps, "
                f"{round(tools.miles(new_length), 3)} miles, "
                f"{len(current_step['candidate_tracks'])} current candidates, "
                f"{len(Blocks)} blocks."
            )
        debug_overall_count += 1

    # helper function that produces a prefilled "step" for moving forward
    def new_step(start_node, existing_length=0, points=None, models=None):

        if points is None:
            points = []

        if models is None:
            models = []

        return [
            {
                "models": models,
                "node": start_node,
                "length": existing_length,
                "candidate_tracks": generate_selection_of_possible_tracks(
                    start_node, candidates_to_generate, params
                ),
                "points": points,
                "blocks_added": [],
            }
        ]

    def update_longest_fail(
        steps,
        result_node,
        new_length,
        points,
        models,
    ):
        nonlocal longest_fail
        nonlocal longest_fail_length

        if new_length <= longest_fail_length:
            return

        longest_fail_length = new_length
        longest_fail = steps[:]

        if len(steps) == 1:
            longest_fail += new_step(
                result_node,
                new_length,
                points,
                models,
            )

    def backtrack(steps, blocks_current_step_index):

        current_step = steps[-1]

        existing_length = current_step["length"]
        target_length = existing_length - backtrack_distance

        while steps[-1]["length"] > target_length and len(steps) > 1:

            blocks_remove(steps[-1]["blocks_added"])
            steps.pop()

            blocks_current_step_index = min(
                blocks_current_step_index,
                len(steps) - 1,
            )

        return blocks_current_step_index

    def try_candidates(current_step, steps, mode):

        while current_step["candidate_tracks"]:

            track_to_test = current_step["candidate_tracks"][-1]

            result = generate_pieces_from_node_and_mdl(
                track_to_test,
                current_step["node"],
                mode,
            )

            if result is None:

                current_step["candidate_tracks"].pop()
                debug_logger(steps, current_step["length"])
                continue

            (
                result_node,
                points,
                models,
                track_length,
            ) = result

            new_length = current_step["length"] + track_length

            steps += new_step(
                result_node,
                new_length,
                points,
                models,
            )

            update_longest_fail(
                steps,
                result_node,
                new_length,
                points,
                models,
            )

            return True

        return False

    steps = new_step(start_node)

    while (
        len(steps) > 0
        and steps[-1]["length"] < track_profile[-1]
        and debug_overall_count < debug_maximum_count
    ):

        blocks_current_step_index = update_blocks(
            steps,
            blocks_current_step_index,
        )

        current_step = steps[-1]

        if try_candidates(current_step, steps, track_profile[0]):
            # continue to the next step
            continue

        # if it happens that you ran out of candidates in the base step:
        if len(steps) == 1 and len(current_step["candidate_tracks"]) == 0:

            print("Steps process has died! Exiting.")
            return longest_fail

        # if your candidates did not succeed, backtrack
        blocks_current_step_index = backtrack(
            steps,
            blocks_current_step_index,
        )

    # if the process has concluded:
    if debug_overall_count >= debug_maximum_count:

        print(
            "Longest usable section loaded: ",
            round(tools.miles(longest_fail[-1]["length"]), 3),
        )

        return longest_fail

    sec = tools.stopwatch_click(
        "trackhammer",
        f"{candidates_to_generate}, {logLength}",
    )

    print(f"Trackhammer finished normally: " f"{logLength} length, {sec} seconds.")

    return steps


def create_rail_path(start_node, track_profile, params={}):

    tools.stopwatch_click("trackhammer")

    # Hollows out a little area near the start of the trackhammer, to prevent old rails from blocking the start of the mains
    blocks_remove(get_block_ids(start_node[0]))

    # system for testing multiple variations of rollbacks and candidates, currently semi-disabled
    rollbacks = [32000]
    candidates = [20]
    random.shuffle(rollbacks)
    random.shuffle(candidates)

    for backtrack_distance in rollbacks:

        for candidates_to_generate in candidates:

            steps_found = generation_process(
                start_node,
                track_profile,
                backtrack_distance,
                candidates_to_generate,
                params,
            )

    tools.stopwatch_click("submodule", "Track path complete")
    return steps_found


def aggregate(track_profile):

    Total = 0
    Lengths = track_profile[1::2]
    Incrementor = 1

    for Entry in Lengths:
        track_profile[Incrementor] = tools.inches(Entry + Total)

        Total += Entry
        Incrementor += 2

    return track_profile


# Taking a node start and target length + parameters, generate a list of track models that coincides with grade, curvature, and block rules.
def generate_mainline(start_node, track_profile, params={}):
    # FYI: Nodes are defined as [[x, y, z], "string TP3 direction", base rotation in 90 increments, IsReversed (compile relevant only)]

    aggregated_profile = aggregate(track_profile)

    print(
        "Began working on generating "
        + str(tools.miles(track_profile[-1]))
        + " mile mainline :",
        start_node,
        params,
    )

    steps_found = create_rail_path(start_node, aggregated_profile, params)

    display_blocks_in_vmf()

    track.write_track_from_trackhammer_steps(steps_found)

    tools.stopwatch_click("submodule", "Pathfinder data written")
