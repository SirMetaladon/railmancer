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

    # The start of a new main should not be blocked by whatever was
    # already reserved on its horizontal cells.
    for cell in horizontal_cells(point):
        HeightTable.pop(cell, None)


# From a list of points, reserve the height cells that are not already
# spoken for and return the records a rollback can restore.
def blocks_new(list_of_points):

    return blocks_new_height(list_of_points)


# Patch function that takes all the imported points and prefills the Blocking system with them, ensuring future Trackhammers do not intersect with existing track.
def exclude_existing():

    current_points = lines.get_all_track_points()
    new_blocks = blocks_new(current_points)
    print(f"Imported {len(current_points)} points, created {len(new_blocks)} Blocks.")


# For this specific point, does the 2x2 of closest blocks contain any reserved blocks? If so, this space is not legal.
def are_points_blocked(list_of_points):

    return points_violate_height(list_of_points)


# Undo one blocks_new. The records are height-table entries, not block ids.
def blocks_remove(list_of_block_ids):

    blocks_restore_height(list_of_block_ids)


def _unit_xy(x, y):

    length = math.hypot(x, y)
    if length < 1e-9:
        return 0.0, 0.0
    return x / length, y / length


def _node_forward(node):

    # Same rotation the piece itself is placed with, so the tangent matches the step.
    local = track.move_in_trackspace(1024.0, node[1])
    world = tools.rot_orth((float(local[0]), float(local[1]), 0.0), node[2])
    return _unit_xy(float(world[0]), float(world[1]))


def point_one_block_ahead(start_node):

    # One BlockHorizontal step along the start node's heading.
    fx, fy = _node_forward(start_node)
    x, y, z = start_node[0]
    return (
        float(x) + fx * BlockHorizontal,
        float(y) + fy * BlockHorizontal,
        z,
    )


def _chord_fractions(start, end):

    # Same stations the old chord walk used. The count stays tied to the
    # block size, so a long piece still costs a handful of samples.
    dist = float(distance.euclidean(start, end))
    cutoff = BlockHorizontal * 0.85
    if cutoff <= 0:
        return []
    iterations = math.floor(dist / cutoff)
    if iterations <= 1:
        return []
    return [step / (iterations + 1) for step in range(1, iterations)]


def _chord_block_points(current_node, next_node):

    extras = []
    start = np.asarray(current_node[0])
    end = np.asarray(next_node[0])
    for fraction in _chord_fractions(start, end):
        extras.append(tools.linterp(start, end, fraction))
    return [next_node[0]] + extras


def _arc_frame(start, end, forward_s, forward_e):

    # Circle implied by the two tangents and the chord. A 90° piece bulges
    # off that chord by R*(1-cos(θ/2)); the old samples walked the chord.
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    fsx, fsy = forward_s
    fex, fey = forward_e
    theta = math.atan2(fsx * fey - fsy * fex, fsx * fex + fsy * fey)
    chord = math.hypot(ex - sx, ey - sy)
    sin_half = math.sin(abs(theta) / 2.0)
    if abs(theta) < 1e-3 or chord < 1.0 or sin_half < 1e-6:
        return None
    radius = (chord / 2.0) / sin_half
    sign = 1.0 if theta > 0.0 else -1.0
    cx = sx + sign * (-fsy) * radius
    cy = sy + sign * (fsx) * radius
    phi0 = math.atan2(sy - cy, sx - cx)
    return theta, radius, cx, cy, phi0, sign


def _arc_sample(frame, start, end, fraction):

    theta, radius, cx, cy, phi0, sign = frame
    phi = phi0 + theta * fraction
    z0 = float(start[2])
    z1 = float(end[2])
    if fraction >= 1.0:
        point = end
    else:
        point = (
            cx + radius * math.cos(phi),
            cy + radius * math.sin(phi),
            z0 + (z1 - z0) * fraction,
        )
    tangent = _unit_xy(-math.sin(phi) * sign, math.cos(phi) * sign)
    return point, tangent


def _outer_indices(mode):

    if not mode:
        return ()
    left, right = int(mode[0]), int(mode[1])
    found = []
    if left > 0:
        found.append(-left)
    if right > 0:
        found.append(right)
    return tuple(found)


def _shift_track(point, forward, index, spacing):

    # Right of the tangent, one track spacing (192 on 0fw) per index.
    fx, fy = forward
    offset = spacing * index
    return (
        float(point[0]) + fy * offset,
        float(point[1]) - fx * offset,
        float(point[2]),
    )


def _piece_samples(current_node, next_node):

    start = np.asarray(current_node[0], dtype=float)
    end = np.asarray(next_node[0], dtype=float)
    forward_s = _node_forward(current_node)
    forward_e = _node_forward(next_node)
    fractions = _chord_fractions(start, end)
    frame = _arc_frame(start, end, forward_s, forward_e)
    if frame is not None:
        theta, radius = frame[0], frame[1]
        sagitta = radius * (1.0 - math.cos(abs(theta) / 2.0))
        # No chord sample near the middle: one bulge point is the whole nudge.
        if sagitta > 16.0 and not any(abs(fraction - 0.5) <= 0.2 for fraction in fractions):
            fractions.append(0.5)
    samples = [(current_node[0], forward_s)]
    if frame is None:
        for fraction in fractions:
            samples.append((tools.linterp(start, end, fraction), forward_s))
        samples.append((next_node[0], forward_e))
        return samples
    for fraction in fractions:
        samples.append(_arc_sample(frame, start, end, fraction))
    samples.append((next_node[0], forward_e))
    return samples


def _samples_clear(points):

    for point in points:
        if not point_inside_border((int(point[0]), int(point[1]))):
            return False
    return not are_points_blocked(points)


# From a pair of track nodes representing a piece of rail, return a short list
# of points for the block check. Straights stay on the chord. A curve samples
# the arc those tangents actually follow. `mode` adds the outermost parallel
# track on each side that has one, not every track in between.
def get_block_points_from_nodes(current_node, next_node, mode=None):

    outers = _outer_indices(mode)
    curved = current_node[1] != next_node[1] or current_node[2] != next_node[2]
    if not curved and not outers:
        return _chord_block_points(current_node, next_node)

    samples = _piece_samples(current_node, next_node)
    # The centerline check never included the start joint; the previous piece owned it.
    points = [sample[0] for sample in samples[1:]]
    if outers:
        spacing = float(track.move_in_trackspace(0, "0fw", 1)[1])
        for index in outers:
            for point, forward in samples:
                points.append(_shift_track(point, forward, index, spacing))
    return points


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
        mode,
    )

    if not _samples_clear(points):
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

    A switch zone uses this before it is accepted. A rejected zone is not
    placed, and the pathfinder backtracks.
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

    global HeightTable

    HeightTable = {}


def display_blocks_in_vmf():

    _display_height_markers()


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

    # The attempt limit is per search. A previous call must not spend it.
    debug_overall_count = 0
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
                f"{len(HeightTable)} blocks."
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
                # Plain track since the previous ladder. Ladders stay at 0.
                "run_plain": 0,
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

    def _run_target(run_id):

        # Specified plain length of this run, not a cumulative total.
        if run_id <= 0:
            return float(cumulative_track_profile[0][1])
        return float(
            cumulative_track_profile[run_id][1] - cumulative_track_profile[run_id - 1][1]
        )

    def _tolerance():

        return float(TEST.get("run_length_tolerance"))

    def _in_window(plain, target):

        tol = _tolerance()
        return (target - tol) <= plain <= (target + tol)

    def _route_finished(step):

        if not fit_run_length_enabled():
            return step["length"] >= cumulative_track_profile[-1][1]
        last = len(cumulative_track_profile) - 1
        if step["current_run_id"] != last:
            return False
        return _in_window(float(step.get("run_plain", 0)), _run_target(last))

    def append_switch_transition(
        current_step, steps, before, after, entered_run, join=None
    ):

        # The ladder sits after the plain track. Its length is not part of
        # either run, so a direction-dependent zone cannot blow the budget.
        from railmancer import switches

        node = current_step["node"]
        try:
            zone = switches.zone_length(before, after, node[1], join)
        except switches.SwitchGeometryError as exc:
            print(exc)
            return False

        span = (max(before[0], after[0]), max(before[1], after[1]))
        if zone > 0 and corridor_is_blocked(node[0], node[1], node[2], span, zone):
            # Off the map, in a block, or the outer tracks leave the border.
            return False
        if zone > 0:
            end = track.updated_position(
                node[0], track.move_in_trackspace(zone, node[1]), node[2]
            )
            end_node = (end, node[1], node[2], False)
            points = _parallel_points(node, end_node, span)
            length = current_step["length"] + zone
        else:
            # A stub join can have nothing to build. Still enter the run.
            end_node = node
            points = []
            length = current_step["length"]
        steps.extend(
            new_step(
                end_node,
                entered_run,
                cumulative_track_profile[entered_run],
                length,
                points,
                "",
            )
        )
        steps[-1]["switch_zone"] = (before, after)
        steps[-1]["switch_join"] = join
        steps[-1]["run_plain"] = 0
        return True

    def _settle(step, steps):

        # A run already inside its window gets its ladder now, or the next
        # run's parameters when the count does not change. Failure here is
        # a dead end: the caller backtracks. Nothing is laid past the boundary.
        run_id = step["current_run_id"]
        if run_id >= len(cumulative_track_profile) - 1:
            return "building"
        plain = float(step.get("run_plain", 0))
        target = _run_target(run_id)
        if plain < target - _tolerance():
            return "building"
        if plain > target + _tolerance():
            return "blocked"
        entered = run_id + 1
        before = tuple(cumulative_track_profile[run_id][0])
        after = tuple(cumulative_track_profile[entered][0])
        if before != after:
            if not append_switch_transition(
                step, steps, before, after, entered, _join_for_run(entered)
            ):
                return "blocked"
            return "advanced"
        step["current_run_id"] = entered
        step["current_run"] = cumulative_track_profile[entered]
        step["run_plain"] = 0
        step["candidate_tracks"] = generate_selection_of_possible_tracks(
            step["node"], candidates_to_generate, step["current_run"]
        )
        return "advanced"

    def _reject(steps, step):

        search_stats["rejected"] += 1
        debug_logger(steps, step["length"])

    def _place_piece(current_step, steps, mode, mdl_to_test):

        result = iterate_backbone(mdl_to_test, current_step["node"], mode)
        if result is None:
            _reject(steps, current_step)
            return False
        result_node, points, track_length = result
        landed = float(current_step.get("run_plain", 0)) + float(track_length)
        steps.extend(
            new_step(
                result_node,
                current_step["current_run_id"],
                current_step["current_run"],
                current_step["length"] + track_length,
                points,
                mdl_to_test,
            )
        )
        steps[-1]["run_plain"] = landed
        search_stats["placements"] += 1
        return True

    def _try_within_tolerance(current_step, steps, mode):

        state = _settle(current_step, steps)
        if state == "advanced":
            update_longest_fail(steps, steps[-1]["length"])
            return True
        if state == "blocked":
            # The run is finished and the ladder will not fit here. More
            # pieces would only cross the boundary. Drop the candidates so
            # a start node that cannot backtrack dies instead of spinning.
            current_step["candidate_tracks"] = []
            _reject(steps, current_step)
            return False

        target = _run_target(current_step["current_run_id"])
        tol = _tolerance()
        while current_step["candidate_tracks"]:
            mdl_to_test = current_step["candidate_tracks"].pop()
            search_stats["attempts"] += 1
            plain = float(current_step.get("run_plain", 0))
            piece_length = float(track.get_length(mdl_to_test))
            # Past the far side of the window there is no legal ladder site.
            # A shorter candidate may still land; if none can, this is a dead end.
            if plain + piece_length > target + tol:
                _reject(steps, current_step)
                continue
            if not _place_piece(current_step, steps, mode, mdl_to_test):
                continue
            landed = float(steps[-1]["run_plain"])
            if landed >= target - tol:
                state = _settle(steps[-1], steps)
                if state == "blocked":
                    steps.pop()
                    search_stats["placements"] -= 1
                    _reject(steps, current_step)
                    continue
            update_longest_fail(steps, steps[-1]["length"])
            return True
        return False

    def _try_unfitted(current_step, steps, mode):

        # trackhammer_fit_run_length is off: place pieces, no ladders.
        while current_step["candidate_tracks"]:
            mdl_to_test = current_step["candidate_tracks"].pop()
            search_stats["attempts"] += 1
            result = iterate_backbone(mdl_to_test, current_step["node"], mode)
            if result is None:
                _reject(steps, current_step)
                continue
            result_node, points, track_length = result
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
            steps.extend(
                new_step(
                    result_node,
                    new_run_id,
                    cumulative_track_profile[new_run_id],
                    new_length,
                    points,
                    mdl_to_test,
                )
            )
            update_longest_fail(steps, new_length)
            return True
        return False

    def try_candidates(current_step, steps, mode):

        if fit_run_length_enabled():
            return _try_within_tolerance(current_step, steps, mode)
        return _try_unfitted(current_step, steps, mode)

    # START OF PROCESS
    steps = new_step(start_node, 0, cumulative_track_profile[0])

    while (
        len(steps) > 0
        and not _route_finished(steps[-1])
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

    # Clear the start cell and the cell one block ahead, so rails already
    # sitting on the first step do not block the main.
    clear_start_footprint(start_node[0])
    clear_start_footprint(point_one_block_ahead(start_node))

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
        + str(round(tools.miles(cumulative_track_profile[-1][1]), 3))
        + " mile mainline :",
        start_node,
    )

    steps_found = create_rail_path(start_node, cumulative_track_profile)

    display_blocks_in_vmf()

    track.write_track_from_trackhammer_steps(steps_found)

    tools.stopwatch_click("submodule", "Pathfinder data written")
