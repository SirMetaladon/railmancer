import random, math, time
from railmancer import tools, track, cfg, lines, vmfpy
from scipy.spatial import distance
import numpy as np

# This is an algoritm for pathing a mainline through the playable area without bumping into itself. Last part pending.

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
def track_placement_is_valid(model, current_node):
    test_node = track.get_new_node_from_node_and_model(model, current_node)

    points = get_block_points_from_nodes(current_node, test_node)

    end = (int(test_node[0][0]), int(test_node[0][1]))
    valid = tools.within2d(end, cfg.get("trackhammer_border"))

    if valid:
        valid = not are_points_blocked(points)

    # if track-end is inside the block and
    return (test_node, valid, points)

# Queries the track system to find valid tracks according to grade and curvature rules, then returns a randomized selection
def generate_selection_of_possible_tracks(node, count, params={}):

    # takes direction, minumum radius level, minimum grade level, maximum grade level
    possible_tracks = track.valid_next_tracks(node[1], params)
    
    return sprinkle_selector(possible_tracks, count)

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

    BlockHorizontal = cfg.get("trackhammer_block_size_horizontal")
    BlockVertical = cfg.get("sector_minimum_height") * 1.05
    Block_Standoff_Distance = cfg.get("trackhammer_block_standoff_distance")

    global Blocks
    Blocks = {}

# Taking a node start and target length + parameters, generate a list of track models that coincides with grade, curvature, and block rules.
def generate_mainline(start_node, length_target_mi, params={}):
    # FYI: Nodes are defined as [[x, y, z], "string TP3 direction", base rotation in 90 increments, IsReversed (compile relevant only)]

    tools.stopwatch_click("trackhammer")

    # Hollows out a little area near the start of the trackhammer, to prevent old rails from blocking the start of the mains
    blocks_remove(get_block_ids(start_node[0]))

    # debugging variables, tuning required sometimes to optimize behavior (magical numbers, boo!)
    debug_maximum_count = 10000000
    debug_reporting_interval = 1000
    length_target_in = length_target_mi * 5280 * 12

    # system for testing multiple variations of rollbacks and candidates, currently semi-disabled
    rollbacks = [6000]
    candidates = [40]
    random.shuffle(rollbacks)
    random.shuffle(candidates)

    for backtrack_distance in rollbacks:

        for candidates_to_generate in candidates:

            debug_overall_count = 0
            blocks_current_step_index = 0
            logLength = 0

            # helper function that produces a prefilled "step" for moving forward
            def new_step(start_node, existing_length = 0, points=[], model=""):
                return [
                    {
                        "model": model,
                        "node": start_node,
                        "length": existing_length,
                        "candidate_tracks": generate_selection_of_possible_tracks(
                            start_node, candidates_to_generate, params
                        ),  # count of these remaining = your fail counter
                        "points": points,
                        "blocks_added": [],
                    }
                ]

            steps = new_step(start_node)

            while steps[-1]["length"] < length_target_in and debug_overall_count < debug_maximum_count:
                # might include a break inside, but this is a failsafe

                blocks_current_step_index = update_blocks(steps, blocks_current_step_index)

                current_step = steps[-1]

                while len(current_step["candidate_tracks"]):

                    track_to_test = current_step["candidate_tracks"][-1]

                    result_node, valid, points = track_placement_is_valid(
                        track_to_test, current_step["node"]
                    )

                    if valid:

                        new_length = current_step["length"] + track.get_length(
                            track_to_test
                        )
                        if debug_overall_count % debug_reporting_interval == 0:
                            logLength = max(logLength, round(new_length / 12 / 5218, 3))
                            print(
                                len(steps),
                                round(new_length / 12 / 5218, 3),
                                len(current_step["candidate_tracks"]),
                                len(Blocks),
                            )
                        debug_overall_count += 1

                        steps += new_step(
                            result_node, new_length, points, track_to_test
                        )
                        break

                    else:

                        current_step["candidate_tracks"].remove(track_to_test)
                
                # If you ran out of attempts to place a track this step, roll back by the specified length
                if len(current_step["candidate_tracks"]) == 0:
                
                    previous_length = current_step["length"]
                    target_length = previous_length - backtrack_distance
                    
                    while blocks_current_step_index > 2 and (steps[-1]["length"] < target_length):
                    
                        blocks_remove(steps[-1]["blocks_added"])
                        steps.pop(-1)
                        
                        blocks_current_step_index = min(blocks_current_step_index,len(steps)

            sec = tools.stopwatch_click(
                "trackhammer", f"{Rollback}, {candidates_to_generate}, {logLength}"
            )

            print(f"{logLength/sec}")

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

    tools.stopwatch_click("submodule", "Mainline generation complete")

    ModelList = []

    for Step in steps[1:]:
        ModelList += [Step["model"]]

    track.write_pathfinder_data(ModelList, start_node)

    tools.stopwatch_click("submodule", "Pathfinder data written")
