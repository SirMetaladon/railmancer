import random, math, time
from collections import deque
from railmancer import tools, track, lines, vmfpy
from railmancer import cfg as TEST
from scipy.spatial import distance
import numpy as np

# This is an algoritm for pathing a mainline through the playable area without bumping into itself. Last part pending.

debug_overall_count: int = 0
logLength: float = 0

# Cheap scored-search state. None of it is consulted while scored selection is off.
HeightMap: dict = {}
HeightColumns: dict = {}
HeightCounts: dict = {}
# Height mode only: one absolute rail height per horizontal cell. No lists.
HeightTable: dict = {}
BorderDistance: dict = {}
FailedStates: set = set()
_border_override = None

search_stats = {
    "attempts": 0,
    "placements": 0,
    "rejected": 0,
    "score_checks": 0,
    "one_step_pops": 0,
    "distance_backtracks": 0,
    "died": 0,
    "stuck": 0,
    "memo_skips": 0,
    "grade_rejects": 0,
}


def _fresh_stats():

    return {key: 0 for key in search_stats}


# determine_grade_level buckets, in percent:
#   exactly 0 -> 0
#   0 < |g| < 2 -> ±1
#   2 <= |g| < 2.6 -> ±2
#   |g| >= 2.6 -> ±3
# The mild end of a level is the boundary shared with the next-shallower bucket.
_MILD_GRADE_PERCENT = {0: 0.0, 1: 0.0, 2: 2.0, 3: 2.6}


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
    """Exact vertical gap used by height mode, in map units.

    Layers mode does not read this. Its gap is vertical_clearance(), two
    block layers, because a point reserves a 2-long run of z layers.
    """

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


def _split_block(block_id):

    parts = block_id.split(",")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _height_reserve(block, z):

    # One block id is one z-layer in a 2D column. The count is how many
    # layers in that column are still reserved. The map stores the max track z.
    x, y, layer = _split_block(block)
    column = HeightColumns.setdefault((x, y), {})
    if layer in column:
        column[layer] = max(column[layer], z)
    else:
        column[layer] = z
    HeightCounts[(x, y)] = len(column)
    HeightMap[(x, y)] = max(column.values())


def _height_release(block):

    x, y, layer = _split_block(block)
    column = HeightColumns.get((x, y))
    if not column or layer not in column:
        return
    column.pop(layer)
    if not column:
        HeightColumns.pop((x, y), None)
        HeightCounts.pop((x, y), None)
        HeightMap.pop((x, y), None)
        return
    HeightCounts[(x, y)] = len(column)
    HeightMap[(x, y)] = max(column.values())


# From a list of points, find all blocks that are NOT already spoken for and reserve them, returning a list of valid newly reserved blocks.
def blocks_new(list_of_points):

    if height_mode_enabled():
        return blocks_new_height(list_of_points)

    new_blocks = []
    owned = set()

    for point in list_of_points:
        z = float(point[2])
        block_ids = get_block_ids(point)

        for block in block_ids:
            if block not in Blocks:
                new_blocks += [block]
                Blocks[block] = True
                owned.add(block)
                _height_reserve(block, z)
            elif block in owned:
                # Two samples of this same piece claimed one cell. Keep the higher z.
                _height_reserve(block, z)

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
            _height_release(entry)


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


def scored_selection_enabled():

    return int(TEST.get("trackhammer_scored_selection")) != 0


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


def cell_of(x, y):

    return (
        math.floor(float(x) / BlockHorizontal),
        math.floor(float(y) / BlockHorizontal),
    )


def vertical_clearance():
    """Minimum rise that guarantees two tracks do not share a block layer.

    get_block_ids reserves a 2-long run of layers: the layer holding the
    point, plus the neighbor on whichever side of the cell center the point
    sits. The highest reserved layer index is floor(z / BlockVertical + 0.5),
    and the lowest is that minus 1.

    Two points miss each other only when those intervals are disjoint, i.e.
    floor(z_hi / BV + 0.5) >= floor(z_lo / BV + 0.5) + 2. The smallest H that
    satisfies this for every fractional position is exactly 2 * BlockVertical.
    At H the intervals touch but do not overlap. Any less, and a point sitting
    just above a half-layer still shares a layer with a point almost 2 blocks
    higher. Example with BV = 1260: z = 630.1 reserves layers 0 and 1, and
    z = 3150.1 (exactly 2*BV higher) reserves layers 2 and 3.

    grade_need uses this H as the height a later track must clear above an
    occupied column's stored track z.
    """

    return 2.0 * BlockVertical


def grade_level_mild_slope(level):
    """Rise/run at the shallow end of a run's min_grade level.

    Positive levels climb; the floor is 0, 0, 2%, 2.6% for levels 0..3.
    Negative levels mirror that, so a forced -3 band floors at -2.6% and
    extra descent is not punished (it is not "above" the floor). False / None
    means the run did not set a minimum, and the floor is flat.
    """

    if level is False or level is None:
        return 0.0
    level = int(level)
    magnitude = _MILD_GRADE_PERCENT.get(abs(level), 2.6 + abs(level) - 3)
    if level < 0:
        return -magnitude / 100.0
    return magnitude / 100.0


def world_xy_forward(direction, yaw):

    heading = track.get_heading(direction)
    if heading is None:
        return (1.0, 0.0)
    rotated = tools.rot_orth(heading, yaw)
    x = float(rotated[0])
    y = float(rotated[1])
    norm = math.hypot(x, y) or 1.0
    return (x / norm, y / norm)


def horizontal_slope(start, end):

    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    dz = float(end[2]) - float(start[2])
    run = math.hypot(dx, dy)
    if run < 1.0:
        return 0.0
    return dz / run


def turn_between(prev_node, new_node):

    f0 = world_xy_forward(prev_node[1], prev_node[2])
    f1 = world_xy_forward(new_node[1], new_node[2])
    cross = f0[0] * f1[1] - f0[1] * f1[0]
    dot = max(-1.0, min(1.0, f0[0] * f1[0] + f0[1] * f1[1]))
    angle = abs(math.atan2(cross, dot))
    if angle < 1e-6:
        return 0.0, 0
    sign = 1 if cross > 0 else -1
    return angle, sign


def state_key(node, run_id):

    # Heading is the TP3 direction string plus world yaw. The string alone is
    # not a world angle: 0fw at yaw 0 travels -X, and the same string at yaw
    # -90 travels +Y. Z layer is floor(z / BlockVertical), the same vertical
    # grid the block ids use.
    x, y, z = node[0]
    cell_x, cell_y = cell_of(x, y)
    yaw = int(node[2]) % 360
    layer = math.floor(float(z) / BlockVertical)
    return (cell_x, cell_y, node[1], yaw, layer, int(run_id))


def run_id_for_length(length, profile):

    if len(profile) == 1:
        return 0

    for runid in range(0, len(profile)):
        if profile[runid][1] > length:
            return runid

    return 0


def rebuild_border_distance():
    """Manhattan steps from each inside cell to the border, computed once.

    Inside means the cell center passes point_inside_border. Cells outside
    the border are absent. Distance 1 touches the border.
    """

    global BorderDistance

    border = float(TEST.get("trackhammer_border"))
    reach = int(math.floor(border / float(BlockHorizontal))) + 3
    inside = []
    for cx in range(-reach, reach + 1):
        for cy in range(-reach, reach + 1):
            center = ((cx + 0.5) * BlockHorizontal, (cy + 0.5) * BlockHorizontal)
            if point_inside_border(center):
                inside.append((cx, cy))

    inside_set = set(inside)
    BorderDistance = {}
    queue = deque()
    for cell in inside:
        cx, cy = cell
        touches = False
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (cx + dx, cy + dy) not in inside_set:
                touches = True
                break
        if touches:
            BorderDistance[cell] = 1
            queue.append(cell)

    while queue:
        cx, cy = queue.popleft()
        base = BorderDistance[(cx, cy)]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cx + dx, cy + dy)
            if nxt in inside_set and nxt not in BorderDistance:
                BorderDistance[nxt] = base + 1
                queue.append(nxt)

    return BorderDistance


def probe_from_node(node):
    """Look a few block-cells out the exit heading, plus one cell each side.

    Returns clear runway cells, the first occupied column's track z and the
    distance to it, and how many sides are hugging a border or a lower layer.
    """

    steps = int(TEST.get("trackhammer_score_probe_cells"))
    fx, fy = world_xy_forward(node[1], node[2])
    x = float(node[0][0])
    y = float(node[0][1])
    z = float(node[0][2])
    clear = 0
    hit_z = None
    hit_distance = None
    seen = set()

    for i in range(1, steps + 1):
        sample_x = x + fx * BlockHorizontal * i
        sample_y = y + fy * BlockHorizontal * i
        cell = cell_of(sample_x, sample_y)
        if cell in seen:
            continue
        seen.add(cell)
        if cell not in BorderDistance:
            break
        top = _probe_hit_height(cell, z)
        if top is not None:
            hit_z = top
            hit_distance = i * float(BlockHorizontal)
            break
        clear += 1

    hugs = 0
    our_layer = math.floor(z / BlockVertical)
    for sign in (1, -1):
        side_x = x + (-fy) * sign * BlockHorizontal
        side_y = y + fx * sign * BlockHorizontal
        side = cell_of(side_x, side_y)
        if side not in BorderDistance:
            hugs += 1
            continue
        if _probe_side_is_clear(side, z, our_layer):
            hugs += 1

    return {
        "clear_cells": clear,
        "probe_cells": steps,
        "hit_z": hit_z,
        "hit_distance": hit_distance,
        "hugs": hugs,
    }


def _probe_hit_height(cell, z):
    """Height that still has to be cleared, or None if the cell is open.

    Layers mode treats any reserved layer as a hit. Height mode uses the
    stored rail height and only hits when this z does not already clear
    trackhammer_height_clearance.
    """

    if height_mode_enabled():
        stored = HeightTable.get(cell)
        if stored is None:
            return None
        gap = height_clearance()
        if height_going_down():
            if float(z) > float(stored) - gap:
                return stored
            return None
        if float(z) < float(stored) + gap:
            return stored
        return None

    return HeightMap.get(cell)


def _probe_side_is_clear(cell, z, our_layer):

    # A side hug is a border (handled by the caller) or track that this
    # rail already clears, so it can run alongside instead of into it.
    if height_mode_enabled():
        stored = HeightTable.get(cell)
        if stored is None:
            return False
        gap = height_clearance()
        if height_going_down():
            return float(z) <= float(stored) - gap
        return float(z) >= float(stored) + gap

    top = HeightMap.get(cell)
    return top is not None and math.floor(float(top) / BlockVertical) < our_layer


def required_grade(probe, z):

    if probe["hit_z"] is None or not probe["hit_distance"]:
        return None
    # Layers mode: H is two block layers. Height mode: the config gap,
    # added above the stored top, or subtracted when direction is down.
    if height_mode_enabled():
        gap = height_clearance()
        if height_going_down():
            return (float(probe["hit_z"]) - gap - float(z)) / float(
                probe["hit_distance"]
            )
        return (float(probe["hit_z"]) + gap - float(z)) / float(probe["hit_distance"])
    return (float(probe["hit_z"]) + vertical_clearance() - float(z)) / float(
        probe["hit_distance"]
    )


def placement_cost(
    slope, probe, z, run_params, heading_change, turn_sign, prev_turn_sign
):
    """Lower is better. None hard-rejects a grade that cannot clear the probe.

    required = (zt + H - z) / d when the look-ahead hits occupied track.
    The candidate's own rise/run has to reach that. Anything steeper than
    max(required, the run band's mild end) pays trackhammer_score_weight_grade
    per 1.0 of rise/run (so 100 means one point per percent of extra grade).
    """

    params = run_params or {}
    required = required_grade(probe, z)
    if required is not None:
        # Upward (and layers mode): the piece has to climb at least `required`.
        # Downward height mode: `required` is a ceiling, and the piece has to
        # descend to it or below.
        if height_mode_enabled() and height_going_down():
            if slope - 1e-9 > required:
                return None
        elif slope + 1e-9 < required:
            return None

    floor = grade_level_mild_slope(params.get("min_grade", False))
    reference = floor if required is None else max(required, floor)
    excess = slope - reference

    cost = 0.0
    if excess > 0:
        cost += excess * float(TEST.get("trackhammer_score_weight_grade"))

    missing = max(0, int(probe["probe_cells"]) - int(probe["clear_cells"]))
    cost += missing * float(TEST.get("trackhammer_score_weight_runway"))
    cost -= int(probe["hugs"]) * float(TEST.get("trackhammer_score_weight_hug"))

    quarter = math.pi / 2.0
    if quarter > 0:
        cost += (heading_change / quarter) * float(
            TEST.get("trackhammer_score_weight_heading")
        )
    if prev_turn_sign and turn_sign and prev_turn_sign != turn_sign:
        cost += float(TEST.get("trackhammer_score_weight_reverse"))

    cost += random.random() * float(TEST.get("trackhammer_score_weight_jitter"))
    return cost


def select_scored_candidates(
    node,
    run_params,
    run_id,
    lateral_mode,
    prev_turn_sign,
    length_so_far,
    run_profile,
    max_length=None,
):

    # Best first. One iterate_backbone plus a short probe per legal model.
    possible = track.valid_next_tracks(node[1], run_params)
    k = int(TEST.get("trackhammer_score_top_k"))
    ranked = []

    for model in possible:
        search_stats["score_checks"] += 1
        if max_length is not None and track.get_length(model) > max_length + 1e-6:
            continue
        result = iterate_backbone(model, node, lateral_mode)
        if result is None:
            continue

        result_node, _points, track_length = result
        new_length = length_so_far + track_length
        new_run_id = run_id_for_length(new_length, run_profile)
        if state_key(result_node, new_run_id) in FailedStates:
            search_stats["memo_skips"] += 1
            continue

        slope = horizontal_slope(node[0], result_node[0])
        probe = probe_from_node(result_node)
        heading_change, turn_sign = turn_between(node, result_node)
        cost = placement_cost(
            slope,
            probe,
            float(result_node[0][2]),
            run_params,
            heading_change,
            turn_sign,
            prev_turn_sign,
        )
        if cost is None:
            search_stats["grade_rejects"] += 1
            continue
        # Near a run boundary, prefer the piece that leaves the least gap
        # in front of the switch zone. Far from the boundary this stays off,
        # so it does not bias the whole mainline toward the longest pieces.
        if max_length is not None and max_length < 12000:
            from railmancer import switches as _switches

            quantum = _switches.grid_quantum(node[1]) or 16
            shortfall = max_length - track.get_length(model)
            cost += shortfall / float(quantum)
        ranked.append((cost, model))

    ranked.sort(key=lambda item: item[0])
    return [model for _cost, model in ranked[:k]]


def clear_occupied():

    global Blocks, HeightMap, HeightColumns, HeightCounts, HeightTable, FailedStates

    Blocks = {}
    HeightMap = {}
    HeightColumns = {}
    HeightCounts = {}
    HeightTable = {}
    FailedStates = set()


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
    rebuild_border_distance()

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

    global debug_overall_count, logLength, search_stats, FailedStates

    search_stats = _fresh_stats()
    FailedStates = set()

    blocks_current_step_index = 0
    consecutive_pops = 0

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
        turn_sign=0,
    ):

        # Scored steps wait until try_candidates, after update_blocks has
        # committed the standoff, so the probe sees the blocks that are live.
        if scored_selection_enabled():
            candidate_tracks = []
            already_scored = False
        else:
            candidate_tracks = generate_selection_of_possible_tracks(
                start_node, candidates_to_generate, current_run
            )
            already_scored = True

        return [
            {
                "node": start_node,
                "length": existing_length,
                "candidate_tracks": candidate_tracks,
                "candidates_scored": already_scored,
                "points": points,
                "blocks_added": [],
                "model": step_model,
                "current_run": current_run,
                "current_run_id": current_run_id,
                "turn_sign": turn_sign,
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
                    "candidates_scored": True,
                    "points": _parallel_points(node, cursor, before),
                    "blocks_added": [],
                    "model": "",
                    "tangent_fill": fill,
                    "current_run": current_step["current_run"],
                    "current_run_id": current_step["current_run_id"],
                    "turn_sign": current_step.get("turn_sign", 0),
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

        if scored_selection_enabled() and not current_step.get("candidates_scored"):
            max_length = None
            if fit_run_length_enabled():
                boundary = next_count_boundary(
                    current_step["length"], current_step["current_run_id"]
                )
                if boundary is not None:
                    limit, before, after, entered_run = boundary
                    join = _join_for_run(entered_run)
                    max_length, _zone = fit_budget(
                        current_step["length"],
                        limit,
                        before,
                        after,
                        current_step["node"][1],
                        join,
                    )
                    if max_length <= 0:
                        if append_switch_transition(
                            current_step,
                            steps,
                            before,
                            after,
                            0,
                            entered_run,
                            join,
                        ):
                            update_longest_fail(steps, steps[-1]["length"])
                            return True
                        # This heading has no ladder, or the zone leaves the
                        # map. Pick pieces without the length cap so the line
                        # can turn onto a direction that does have one.
                        max_length = None
            current_step["candidate_tracks"] = select_scored_candidates(
                current_step["node"],
                current_step["current_run"][2],
                current_step["current_run_id"],
                mode,
                current_step.get("turn_sign", 0),
                current_step["length"],
                cumulative_track_profile,
                max_length,
            )
            current_step["candidates_scored"] = True

        while current_step["candidate_tracks"]:

            # Old sampler is consumed from the end, which is how sprinkle's
            # list was always walked. Scored lists are stored best-first.
            if scored_selection_enabled():
                mdl_to_test = current_step["candidate_tracks"].pop(0)
            else:
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
                _heading_change, new_turn = turn_between(
                    current_step["node"], result_node
                )
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
                    new_turn,
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
            # continue to the next step
            consecutive_pops = 0
            continue

        # if it happens that you ran out of candidates in the base step:
        if len(steps) == 1 and len(current_step["candidate_tracks"]) == 0:

            print("Steps process has died! Exiting.")
            search_stats["died"] = 1
            return longest_fail

        # Scored search undoes one piece and tries the parent's next-best.
        # After N consecutive undos, fall back to the distance rewind.
        if scored_selection_enabled():
            pop_limit = int(TEST.get("trackhammer_score_pop_limit"))
            if consecutive_pops >= pop_limit:
                FailedStates.clear()
                consecutive_pops = 0
                search_stats["distance_backtracks"] += 1
                blocks_current_step_index = backtrack(
                    steps,
                    blocks_current_step_index,
                )
            else:
                FailedStates.add(
                    state_key(
                        current_step["node"],
                        current_step["current_run_id"],
                    )
                )
                search_stats["one_step_pops"] += 1
                consecutive_pops += 1
                blocks_remove(steps[-1].get("blocks_added") or [])
                steps.pop()
                blocks_current_step_index = min(
                    blocks_current_step_index,
                    len(steps) - 1,
                )
        else:
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
