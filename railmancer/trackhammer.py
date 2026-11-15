import random, math, time
from railmancer import tools, track, lines, vmfpy
from railmancer import cfg as TEST
from scipy.spatial import distance
import numpy as np

# This is an algoritm for pathing a mainline through the playable area without bumping into itself. Last part pending.

debug_overall_count: int = 0
logLength: float = 0

# Height mode: one absolute rail height per horizontal cell. No lists.
HeightTable: dict = {}
_border_override = None

search_stats = {
    "attempts": 0,
    "placements": 0,
    "rejected": 0,
    "died": 0,
    "stuck": 0,
}


def _fresh_stats():

    return {key: 0 for key in search_stats}


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


def height_mode_enabled():

    return True  # str(TEST.get("trackhammer_block_mode")) == "height"


def height_going_down():

    return str(TEST.get("trackhammer_height_direction")) == "down"


def height_clearance():
    """Exact vertical gap used by height mode, in map units."""

    return float(TEST.get("trackhammer_height_clearance"))


def horizontal_cells(point):
    """The same 2x2 of horizontal cells get_block_ids would reserve.

    Height mode ignores the vertical pair and writes the rail's real z
    into these cells instead.
    """

    x, y, _z = point
    fx = float(x) / BlockHorizontal
    fy = float(y) / BlockHorizontal
    bx = math.floor(fx)
    by = math.floor(fy)
    xs = [bx, bx + 1] if fx - bx > 0.5 else [bx - 1, bx]
    ys = [by, by + 1] if fy - by > 0.5 else [by - 1, by]
    return [(cx, cy) for cx in xs for cy in ys]


def _height_extreme(current, z):

    if current is None:
        return z
    if height_going_down():
        return min(current, z)
    return max(current, z)


def blocks_new_height(list_of_points):
    """Reserve cells in the 2-D height table.

    Each returned record is (cell_x, cell_y, prior). prior is None when the
    cell was empty, otherwise the height this call replaced. A cell is
    recorded once per call: later samples in the same piece only move the
    stored extreme. Rollback restores `prior` and does not need another table.

    That restore is exact when undos run newest-first, which is what
    backtrack, the one-step pop, and update_blocks' backward walk all do.
    If an older step were removed while a newer overwrite of the same cell
    was still applied, restoring the older prior would wipe the newer height.
    His removal order does not do that.
    """

    records = []
    touched = set()

    for point in list_of_points:
        z = float(point[2])
        for cell in horizontal_cells(point):
            if cell in touched:
                current = HeightTable.get(cell)
                updated = _height_extreme(current, z)
                if updated != current:
                    HeightTable[cell] = updated
                continue

            prior = HeightTable.get(cell)
            updated = _height_extreme(prior, z)
            if prior is not None and updated == prior:
                continue

            HeightTable[cell] = updated
            records.append((cell[0], cell[1], prior))
            touched.add(cell)

    return records


def blocks_restore_height(records):

    for cell_x, cell_y, prior in records:
        cell = (cell_x, cell_y)
        if prior is None:
            HeightTable.pop(cell, None)
        else:
            HeightTable[cell] = prior


def points_violate_height(list_of_points):

    gap = height_clearance()
    downward = height_going_down()

    for point in list_of_points:
        z = float(point[2])
        for cell in horizontal_cells(point):
            stored = HeightTable.get(cell)
            if stored is None:
                continue
            if downward:
                if z > stored - gap:
                    return True
            elif z < stored + gap:
                return True

    return False


def clear_start_footprint(point):

    # Same job as the old get_block_ids wipe: the start of a new main
    # should not be blocked by whatever was already reserved there.
    if height_mode_enabled():
        for cell in horizontal_cells(point):
            HeightTable.pop(cell, None)
        return

    blocks_remove(get_block_ids(point))


# From a list of points, find all blocks that are NOT already spoken for and reserve them, returning a list of valid newly reserved blocks.
def blocks_new(list_of_points):

    if height_mode_enabled():
        return blocks_new_height(list_of_points)

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

    if height_mode_enabled():
        return points_violate_height(list_of_points)

    for point in list_of_points:
        block_ids = get_block_ids(point)
        for block in block_ids:
            if block in Blocks:
                return True

    return False


# For a list of string block ID's, remove them from the currently reserved list of blocks
def blocks_remove(list_of_block_ids):

    global Blocks

    if height_mode_enabled():
        blocks_restore_height(list_of_block_ids)
        return

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
def iterate_backbone(model, prev_node, mode):

    prev_direction = prev_node[1]
    end_direction = track.get_end_direction(model, prev_direction)
    current_direction = track.get_end_direction(model, end_direction)

    start_addlength, end_addlength = track.get_addlength(
        current_direction, end_direction, mode
    )

    current_node = track.get_new_node_from_node_and_model(
        model, prev_node, False, start_addlength, end_addlength
    )

    points = get_block_points_from_nodes(
        prev_node,
        current_node,
    )

    end = (
        int(current_node[0][0]),
        int(current_node[0][1]),
    )

    if not point_inside_border(end):
        return None

    if are_points_blocked(points):
        return None

    median_extra_length = 0
    track_length = track.get_length(model) + median_extra_length

    return (
        current_node,
        points,
        track_length,
    )


# Queries the track system to find valid tracks according to grade and curvature rules, then returns a randomized selection
def generate_selection_of_possible_tracks(node, count, current_run={}):

    # takes direction, minumum radius level, minimum grade level, maximum grade level
    possible_tracks = track.valid_next_tracks(node[1], current_run[2])
    options = tools.sprinkle_selector(possible_tracks, count)

    if len(options) == 0:
        print("Failed to find selection: ", node, count, current_run)

    return options


def fit_run_length_enabled():

    try:
        return int(TEST.get("trackhammer_fit_run_length")) != 0
    except Exception:
        return True


def corridor_is_blocked(origin, direction, heading, mode, distance):
    """True when any parallel track in the stretch leaves the border or hits a block.

    Switch zones and their tangent fill use this before they are accepted.
    A rejected zone is not placed, and the pathfinder backtracks.
    """

    from railmancer import switches

    if distance <= 0:
        return False
    samples = []
    for start, end in switches.corridor_segments(
        origin, direction, heading, mode, distance
    ):
        samples.extend(
            get_block_points_from_nodes(
                (start, direction, heading, False),
                (end, direction, heading, False),
            )
        )
    for point in samples:
        if not point_inside_border((int(point[0]), int(point[1]))):
            return True
    return are_points_blocked(samples)


def point_inside_border(point_xy):

    # Same integer square test iterate_backbone used to call directly.
    # A benchmark can install a predicate (rectangle, L) without touching that test.
    x = int(point_xy[0])
    y = int(point_xy[1])
    if _border_override is not None:
        return bool(_border_override((x, y)))
    return tools.within2d((x, y), TEST.get("trackhammer_border"))


def set_border_override(predicate):

    global _border_override
    _border_override = predicate



def clear_occupied():

    global Blocks, HeightTable

    Blocks = {}
    HeightTable = {}


def display_blocks_in_vmf():

    if height_mode_enabled():
        _display_height_markers()
        return

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


def _display_height_markers():

    # One dev_measurewall brush per occupied cell, same texture and plan
    # size as the layer cubes. The slab starts at the stored rail height
    # and is one block-layer thick. Downward mode hangs the slab below the
    # rail, which is the side the exclusion actually reserves.
    thickness = float(BlockVertical)
    downward = height_going_down()

    TestCount = 0

    for (cell_x, cell_y), stored in HeightTable.items():
        TestCount += 1
        if TestCount > 1000000:
            break
        x = cell_x * BlockHorizontal
        y = cell_y * BlockHorizontal
        if downward:
            z0 = float(stored) - thickness
            z1 = float(stored)

            # to make it fill in the environment
            z1 = 16320
        else:
            z0 = float(stored)
            z1 = float(stored) + thickness

            # to make it fill in the environment
            z0 = -16320

        vmfpy.add_brush(
            [
                x,
                x + BlockHorizontal,
                y,
                y + BlockHorizontal,
                z0,
                z1,
                "dev/dev_measurewall01d",
                0,
                0,
                "24",
            ]
        )

    print(f"Added {len(HeightTable)} height-mode block markers.")


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
    clear_occupied()
    set_border_override(None)

    # Generate a mapping for finding the closest point relative to an existing point.
    # required for exclusion to work
    lines.encode_lines()


def generation_process(
    start_node,
    cumulative_track_profile,
    backtrack_distance,
    candidates_to_generate,
):

    print("Started permutation: ", backtrack_distance, candidates_to_generate)

    global debug_overall_count, logLength, search_stats

    search_stats = _fresh_stats()

    blocks_current_step_index = 0

    longest_fail = []
    longest_fail_length = 0

    debug_reporting_interval = 10000
    debug_maximum_count = int(TEST.get("trackhammer_attempt_limit"))

    def debug_logger(steps, new_length):

        global logLength
        global debug_overall_count

        if debug_overall_count % debug_reporting_interval == 0:
            logLength = max(logLength, round(tools.miles(new_length), 3))
            print(
                f"\n{len(steps[0]["candidate_tracks"])} base candidates,"
                f"{len(steps)} current steps, "
                f"{round(tools.miles(new_length), 3)} miles, "
                f"{len(current_step['candidate_tracks'])} current candidates, "
                f"{len(Blocks)} blocks."
            )
        debug_overall_count += 1

    # helper function that produces a prefilled "step" for moving forward
    def new_step(
        start_node,
        current_run_id,
        current_run,
        existing_length=0,
        points=[],
        step_model="",
    ):

        return [
            {
                "node": start_node,
                "length": existing_length,
                "candidate_tracks": generate_selection_of_possible_tracks(
                    start_node, candidates_to_generate, current_run
                ),
                "points": points,
                "blocks_added": [],
                "model": step_model,
                "current_run": current_run,
                "current_run_id": current_run_id,
            }
        ]

    def update_longest_fail(steps, new_length):
        nonlocal longest_fail
        nonlocal longest_fail_length

        if new_length <= longest_fail_length:
            return

        longest_fail_length = new_length
        longest_fail = steps[:]

    def determine_current_run_id(length):

        if len(cumulative_track_profile) == 1:
            return 0

        for runid in range(0, len(cumulative_track_profile)):
            if cumulative_track_profile[runid][1] > length:
                return runid

        return 0

    def backtrack(steps, blocks_current_step_index):

        current_step = steps[-1]
        steps_before = len(steps)

        existing_length = current_step["length"]
        target_length = existing_length - backtrack_distance

        while steps[-1]["length"] > target_length and len(steps) > 1:

            blocks_remove(steps[-1]["blocks_added"])

            steps.pop()

            blocks_current_step_index = min(
                blocks_current_step_index,
                len(steps) - 1,
            )

        if len(steps) == steps_before:
            print("No steps removed?!?")

        return blocks_current_step_index

    def next_count_boundary(length, run_id):

        # The next run boundary that actually changes the track count.
        for index in range(run_id, len(cumulative_track_profile) - 1):
            boundary = cumulative_track_profile[index][1]
            if boundary <= length:
                continue
            before = tuple(cumulative_track_profile[index][0])
            after = tuple(cumulative_track_profile[index + 1][0])
            if before != after:
                return boundary, before, after, index + 1
        return None

    def _join_for_run(run_id):

        params = cumulative_track_profile[run_id][2]
        if isinstance(params, dict):
            return params.get("join")
        return None

    def _parallel_points(start_node, end_node, mode):

        from railmancer import switches

        distance = float(
            np.linalg.norm(
                np.subtract(np.asarray(end_node[0])[:2], np.asarray(start_node[0])[:2])
            )
        )
        points = []
        for start, end in switches.corridor_segments(
            start_node[0], start_node[1], start_node[2], mode, distance
        ):
            points.extend(
                get_block_points_from_nodes(
                    (start, start_node[1], start_node[2], False),
                    (end, start_node[1], start_node[2], False),
                )
            )
        return points

    def fit_budget(length, limit, before, after, direction, join):

        from railmancer import switches

        try:
            zone = switches.zone_length(before, after, direction, join)
        except switches.SwitchGeometryError:
            zone = 0
        return limit - length - zone, zone

    def append_switch_transition(
        current_step, steps, before, after, budget, entered_run, join=None
    ):

        from railmancer import switches

        node = current_step["node"]
        try:
            zone = switches.zone_length(before, after, node[1], join)
        except switches.SwitchGeometryError as exc:
            print(exc)
            return False

        quantum = switches.grid_quantum(node[1])
        # Largest grid step that still leaves the zone inside the run.
        # `budget` is the room in front of the zone. Rounding up would
        # push the zone past the run target.
        if budget <= 0 or quantum <= 0:
            fill = 0
        else:
            fill = int(math.floor(budget / float(quantum)) * quantum)
        span = (max(before[0], after[0]), max(before[1], after[1]))
        if corridor_is_blocked(node[0], node[1], node[2], before, fill):
            return False
        cursor = node
        length = current_step["length"]
        if fill:
            end = track.updated_position(
                cursor[0], track.move_in_trackspace(fill, cursor[1]), cursor[2]
            )
            cursor = (end, cursor[1], cursor[2], False)
            length += fill
            steps.append(
                {
                    "node": cursor,
                    "length": length,
                    "candidate_tracks": [],
                    "points": _parallel_points(node, cursor, before),
                    "blocks_added": [],
                    "model": "",
                    "tangent_fill": fill,
                    "current_run": current_step["current_run"],
                    "current_run_id": current_step["current_run_id"],
                }
            )
        if corridor_is_blocked(cursor[0], cursor[1], cursor[2], span, zone):
            if fill:
                steps.pop()
            return False
        end = track.updated_position(
            cursor[0], track.move_in_trackspace(zone, cursor[1]), cursor[2]
        )
        end_node = (end, cursor[1], cursor[2], False)
        length += zone
        # Stay in the run this ladder entered. determine_current_run_id
        # returns 0 once length passes the last marker, which would put the
        # next pieces back on the first run's track count.
        steps.extend(
            new_step(
                end_node,
                entered_run,
                cumulative_track_profile[entered_run],
                length,
                _parallel_points(cursor, end_node, span),
                "",
            )
        )
        steps[-1]["switch_zone"] = (before, after)
        steps[-1]["switch_join"] = join
        return True

    def try_candidates(current_step, steps, mode):

        while current_step["candidate_tracks"]:

            mdl_to_test = current_step["candidate_tracks"].pop()

            search_stats["attempts"] += 1
            boundary = next_count_boundary(
                current_step["length"], current_step["current_run_id"]
            )
            if boundary is not None and fit_run_length_enabled():
                limit, before, after, entered_run = boundary
                join = _join_for_run(entered_run)
                budget, _zone = fit_budget(
                    current_step["length"],
                    limit,
                    before,
                    after,
                    current_step["node"][1],
                    join,
                )
                piece_length = track.get_length(mdl_to_test)
                if budget <= 0 or piece_length > budget:
                    shorter_remains = budget > 0 and any(
                        track.get_length(candidate) <= budget
                        for candidate in current_step["candidate_tracks"]
                    )
                    if shorter_remains:
                        continue
                    if append_switch_transition(
                        current_step,
                        steps,
                        before,
                        after,
                        max(budget, 0),
                        entered_run,
                        join,
                    ):
                        update_longest_fail(steps, steps[-1]["length"])
                        return True
                    if budget > 0:
                        continue
            result = iterate_backbone(mdl_to_test, current_step["node"], mode)

            if result is None:

                search_stats["rejected"] += 1
                debug_logger(steps, current_step["length"])
                continue

            else:

                (
                    result_node,
                    points,
                    track_length,
                ) = result

                new_length = current_step["length"] + track_length
                search_stats["placements"] += 1

                new_run_id = determine_current_run_id(new_length)
                if current_step["current_run_id"] != new_run_id:
                    print(
                        "Went over a boundary!",
                        result_node,
                        new_run_id,
                        current_step["current_run_id"],
                    )

                steps += new_step(
                    result_node,
                    new_run_id,
                    cumulative_track_profile[new_run_id],
                    new_length,
                    points,
                    mdl_to_test,
                )

                update_longest_fail(steps, new_length)

                return True

        return False

    # START OF PROCESS
    steps = new_step(start_node, 0, cumulative_track_profile[0])

    while (
        len(steps) > 0
        and steps[-1]["length"] < cumulative_track_profile[-1][1]
        and debug_overall_count < debug_maximum_count
    ):

        blocks_current_step_index = update_blocks(
            steps,
            blocks_current_step_index,
        )

        current_step = steps[-1]

        if try_candidates(current_step, steps, current_step["current_run"][0]):
            continue

        # if it happens that you ran out of candidates in the base step:
        if len(steps) == 1 and len(current_step["candidate_tracks"]) == 0:

            print("Steps process has died! Exiting.")
            search_stats["died"] = 1
            return longest_fail

        # if your candidates did not succeed, backtrack
        blocks_current_step_index = backtrack(
            steps,
            blocks_current_step_index,
        )

    # if the process has concluded:
    if debug_overall_count >= debug_maximum_count:

        report = longest_fail if longest_fail else steps
        reached = 0 if not report else round(tools.miles(report[-1]["length"]), 3)
        print(
            "Longest usable section loaded: ",
            reached,
        )
        search_stats["stuck"] = 1

        return report

    sec = tools.stopwatch_click(
        "trackhammer",
        f"{candidates_to_generate}, {logLength}",
    )

    print(
        f"Trackhammer finished normally: "
        f"{round(steps[-1]["length"]/(12*5280),2)} length, {sec} seconds."
    )

    return steps


def create_rail_path(start_node, cumulative_track_profile):

    tools.stopwatch_click("trackhammer")

    # Hollows out a little area near the start of the trackhammer, to prevent old rails from blocking the start of the mains
    clear_start_footprint(start_node[0])

    # system for testing multiple variations of rollbacks and candidates, currently semi-disabled
    rollbacks = [5000]
    candidates = [20]
    random.shuffle(rollbacks)
    random.shuffle(candidates)

    for backtrack_distance in rollbacks:

        for candidates_to_generate in candidates:

            steps_found = generation_process(
                start_node,
                cumulative_track_profile,
                backtrack_distance,
                candidates_to_generate,
            )

    tools.stopwatch_click("submodule", "Track path complete")
    return steps_found


def aggregate_track_profile(Runs):
    """
    each list entry:
    [(TracksLeft, TracksRight), Length(miles), {params}],
    """

    cumulative_track_profile = []
    prev = 0

    for Run in Runs:

        data = Run[:]
        prev = tools.inches(Run[1]) + prev
        data[1] = prev
        cumulative_track_profile += [data]

    return cumulative_track_profile


# Taking a node start and target length + parameters, generate a list of track models that coincides with grade, curvature, and block rules.
def generate_mainline(start_node, simple_track_profile):
    # FYI: Nodes are defined as [[x, y, z], "string TP3 direction", base rotation in 90 increments, IsReversed (compile relevant only)]

    cumulative_track_profile = aggregate_track_profile(simple_track_profile)

    print(cumulative_track_profile)

    print(
        "Began working on generating "
        + str(tools.miles(cumulative_track_profile[-1][1]))
        + " mile mainline :",
        start_node,
    )

    steps_found = create_rail_path(start_node, cumulative_track_profile)

    display_blocks_in_vmf()

    track.write_track_from_trackhammer_steps(steps_found)

    tools.stopwatch_click("submodule", "Pathfinder data written")
