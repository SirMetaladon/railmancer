import math, random
from railmancer import tools, cfg, lines, vmfpy, terrain
from scipy.spatial import KDTree, cKDTree
import numpy as np

# Handles the creation and management of Sector objects, how they connect to each other, things related to stitching them together, and anything that takes sector objects instead of just raw grids.

Sectors = {}
sector_lookup_grid = {}

# Filled by link(). The wall-clearance report prints these beside the distances.
corkscrew_breaks = 0
corkscrew_errors = 0

# Clearance histogram. The upper edge of each bucket belongs to the next one.
# The last bucket is every distance at or above 1632, including the cap.
WALL_BIN_EDGES = (0, 64, 256, 512, 700, 1024, 1632)
WALL_COLLISION = 64
WALL_WORST = 8

# neighbor slot for a cardinal step (dx, dy): north, east, south, west.
_CARDINAL_SLOT = {(0, 1): 0, (1, 0): 1, (0, -1): 2, (-1, 0): 3}


def _vertical_overlap(first_sector, second_sector):

    # Stored floor and ceiling are map units / 16. The overlap is in those
    # same units; callers that compare to a config height multiply by 16.
    floor_limit = max(first_sector["floor"], second_sector["floor"])
    ceiling_limit = min(first_sector["ceiling"], second_sector["ceiling"])
    return ceiling_limit - floor_limit


def sectors_are_connected(first_sector, second_sector):

    # A neighbor has to share enough vertical room for a sector, and its
    # floor cannot be a cliff away. Ceiling height does not cut the link:
    # a low sky next to a high sky is still one piece of ground.
    if (_vertical_overlap(first_sector, second_sector) * 16) < cfg.get(
        "sector_minimum_height"
    ):
        return False

    floor_gap = abs(first_sector["floor"] - second_sector["floor"]) * 16
    return floor_gap <= cfg.get("sector_connection_maximum_cliff")


def get_sector_relative_to_this_sector(sector_data, nudge):

    # The next column can hold a stack. Share the wall with the sector
    # whose floor is closest to this one. sectors_are_connected still
    # applies, including the cliff limit. An equal floor gap keeps the
    # larger vertical overlap, then the earlier sector in the column.

    sector_list = sector_lookup_grid.get(
        f"{sector_data["x"]+nudge[0]}x{sector_data["y"]+nudge[1]}", False
    )

    if sector_list is False:
        return False

    best_id = False
    best_key = None

    for possible_sector_id in sector_list:

        other = Sectors[possible_sector_id]
        if not sectors_are_connected(sector_data, other):
            continue

        # Overlap is negated so a larger overlap sorts first. A strict <
        # leaves an equal key with the earlier sector.
        key = (
            abs(sector_data["floor"] - other["floor"]),
            -_vertical_overlap(sector_data, other),
        )
        if best_key is None or key < best_key:
            best_key = key
            best_id = possible_sector_id

    return best_id


def convert_real_to_sector_xy(position):

    # magic math box that converts between real and sector-grid space

    # sector x/y are integers relative to the overall grid (-3 to 4)
    # virtual x/y are floats fractions within the sector (0 to 1)
    # noise x/y are integers related to points within the sector (0 to span-1)

    real_x, real_y, _ = position

    sector_x = math.floor(real_x / cfg.get("sector_real_size"))
    sector_y = math.floor(real_y / cfg.get("sector_real_size"))
    return sector_x, sector_y


def get_sector_id_at_position(position):

    # simple conversion of 3d space point to "if within sector, this one, else no"

    sector_x, sector_y = convert_real_to_sector_xy(position)

    sector_list = sector_lookup_grid.get(f"{sector_x}x{sector_y}", False)

    if sector_list is False:
        return False

    real_z = position[2]

    for possible_sector_id in sector_list:

        ceiling = Sectors[possible_sector_id]["ceiling"]
        floor = Sectors[possible_sector_id]["floor"]

        if (ceiling * 16 > real_z) and (floor * 16 < real_z):

            return possible_sector_id

    # if no sectors found or none were within height range
    return False


def new_sector(x, y, floor, ceiling):

    global Sectors
    global sector_lookup_grid

    # creates a new sector object at the x,y sector-grid coordinates using the correct heights.
    bound = cfg.get("max_mapsize") / 2
    minimum = cfg.get("sector_minimum_height") / 16

    floor_real = math.floor(tools.clamped(min(floor, ceiling), -bound, bound - 64) / 16)
    ceiling_real = math.floor(
        tools.clamped(max(floor, ceiling), -bound, bound - 64) / 16
    )

    sector_lookup = f"{x}x{y}"

    sector_id = f"{sector_lookup}x{floor_real}"

    if (ceiling_real - floor_real) < minimum:
        print("Sector squashed against the top or bottom of the level at " + sector_id)
        return False

    if Sectors.get(sector_id, False) != False:
        print("Duplicate Block/floor combination detected! Ignoring: " + sector_id)
        return False

    if sector_lookup_grid.get(sector_lookup, False):
        sector_lookup_grid[sector_lookup] += [sector_id]
    else:
        sector_lookup_grid[sector_lookup] = [sector_id]

    Sectors[sector_id] = {
        "id": sector_id,
        "x": x,
        "y": y,
        "floor": floor_real,
        "ceiling": ceiling_real,
        "grid": {},
        "neighbors": [],
    }


def link():

    # takes all sectors, finds nearby sectors, and adds them to a list of neighbors, then checks those lists for consistiency

    global corkscrew_breaks, corkscrew_errors
    corkscrew_breaks = 0
    corkscrew_errors = 0

    # initially add neighbors
    for Sector_Data in Sectors.values():

        Sector_Data["neighbors"] += [
            get_sector_relative_to_this_sector(Sector_Data, [0, 1]),  # north
            get_sector_relative_to_this_sector(Sector_Data, [1, 0]),  # east
            get_sector_relative_to_this_sector(Sector_Data, [0, -1]),  # south
            get_sector_relative_to_this_sector(Sector_Data, [-1, 0]),  # west
        ]

    # checks for consistiency

    for Sector_Data in Sectors.values():

        for Direction_ID in range(4):  # cycling through Sector_Data["neighbors"]

            Nearby_Sector = Sector_Data["neighbors"][Direction_ID]

            if Nearby_Sector is False:
                continue

            # if this sector's ID is not in the other sector's list of neighbors (disagreement on linking)
            if Sector_Data["id"] not in Sectors[Nearby_Sector]["neighbors"]:

                Sector_Data["neighbors"][Direction_ID] = False

    # a 4-step loop onto a stacked sector pinches the shared corner
    break_corkscrews()

    tools.stopwatch_click("submodule", "Sectors Linked")


def corkscrew_link_clearance(left, right, slot, buckets):

    # nearest sampled track point in either sector, measured to the shared wall.
    # east/west walls sit at x = (west sector x + 1) * sector size. north/south
    # walls are the same idea on y. no points in either sector means infinite.

    size = cfg.get("sector_real_size")

    if slot % 2 == 1:
        wall = (min(left["x"], right["x"]) + 1) * size
        axis = 0
    else:
        wall = (min(left["y"], right["y"]) + 1) * size
        axis = 1

    best = None

    for sector in (left, right):

        for point in buckets.get(sector["id"], ()):

            dist = abs(point[axis] - wall)

            if best is None or dist < best:
                best = dist

    if best is None:
        return float("inf")

    return best


def break_corkscrews():

    # slots 0..3 are north, east, south, west. walk d, d+1, d+2, d+3.
    # finishing on a different sector at the same x,y is a corkscrew.
    # a walk that comes back to the same sector is a plain square (or part
    # of a wider loop) and is left alone.

    global corkscrew_breaks, corkscrew_errors

    buckets = None
    limit = cfg.get("sector_corkscrew_track_clearance")
    prefer_height = cfg.get("sector_corkscrew_prefer_height")
    size = cfg.get("sector_real_size")
    slot_names = ("north", "east", "south", "west")

    for start in Sectors.values():

        for d in range(4):

            current = start
            links = []
            blocked = False

            for step in range(4):

                slot = (d + step) % 4
                neighbor_id = current["neighbors"][slot]

                if neighbor_id is False:
                    blocked = True
                    break

                neighbor = Sectors[neighbor_id]
                links.append((current, neighbor, slot))
                current = neighbor

            if blocked:
                continue

            if current["id"] == start["id"]:
                continue

            if current["x"] != start["x"] or current["y"] != start["y"]:
                continue

            # track points are only needed once a corkscrew actually exists
            if buckets is None:

                buckets = {}

                for point in lines.get_all_track_points():

                    sector_id = get_sector_id_at_position(point)

                    if sector_id is False:
                        continue

                    if buckets.get(sector_id, False):
                        buckets[sector_id].append(point)
                    else:
                        buckets[sector_id] = [point]

            chosen = None

            for left, right, slot in links:

                clearance = corkscrew_link_clearance(left, right, slot, buckets)

                if clearance < limit:
                    continue

                floor_gap = abs(left["floor"] - right["floor"])

                if chosen is None:
                    chosen = (floor_gap, clearance, left, right, slot)
                    continue

                if prefer_height:
                    better = floor_gap > chosen[0]
                else:
                    better = clearance > chosen[1]

                if better:
                    chosen = (floor_gap, clearance, left, right, slot)

            if chosen is None:

                corkscrew_errors += 1
                corner_x = max(item[0]["x"] for item in links) * size
                corner_y = max(item[0]["y"] for item in links) * size
                print(
                    "!!! CORKSCREW ERROR !!! build continues, this corner stays pinched."
                )
                print(
                    f"corner x={corner_x} y={corner_y} (map units). "
                    f"stacked {start['id']} floor {start['floor'] * 16} ceiling {start['ceiling'] * 16}; "
                    f"{current['id']} floor {current['floor'] * 16} ceiling {current['ceiling'] * 16}."
                )
                continue

            _, clearance, left, right, slot = chosen
            left["neighbors"][slot] = False
            right["neighbors"][(slot + 2) % 4] = False
            corkscrew_breaks += 1
            print(
                f"Broke corkscrew {left['id']} {slot_names[slot]} to {right['id']}, clearance {round(clearance,0)}."
            )


def sectors_share_a_wall(first, second):

    # Cardinal neighbors that each list the other in the matching slot.
    # A one-way link was already dropped by link(), and a diagonal step
    # is not a shared wall.
    slot = _CARDINAL_SLOT.get((second["x"] - first["x"], second["y"] - first["y"]))
    if slot is None:
        return False
    back = (slot + 2) % 4
    return (
        first["neighbors"][slot] == second["id"]
        and second["neighbors"][back] == first["id"]
    )


def _unlinked_wall_segments(sector):

    # An unlinked side is a wall. Slot order matches link(): N, E, S, W.
    size = cfg.get("sector_real_size")
    x0 = sector["x"] * size
    y0 = sector["y"] * size
    x1 = x0 + size
    y1 = y0 + size
    sides = (
        ((x0, y1), (x1, y1)),
        ((x1, y0), (x1, y1)),
        ((x0, y0), (x1, y0)),
        ((x0, y0), (x0, y1)),
    )
    return [sides[slot] for slot in range(4) if sector["neighbors"][slot] is False]


def _point_segment_distance(px, py, start, end):

    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    span = dx * dx + dy * dy
    if span == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / span
    if t < 0:
        t = 0
    elif t > 1:
        t = 1
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def track_sample_curves():

    # One polyline per bezier. The joint between two pieces is not a step
    # along the rail, so crossings are counted inside a curve only.
    step = cfg.get("line_maximum_poll_point_distance")
    return [
        lines.convert_bezier_to_points(bezier, step) for bezier in lines.Beziers
    ]


def _wall_bin_labels():

    labels = []
    edges = WALL_BIN_EDGES
    for index in range(len(edges) - 1):
        labels.append(f"{edges[index]}-{edges[index + 1]}")
    labels.append(f"{edges[-1]}+")
    return labels


def measure_wall_clearance(curves=None):

    # 2D distance from each sampled track point to the nearest wall, capped
    # at sector_real_size. A wall is an unlinked side of the point's own
    # sector or of a sector linked to it. The sample is the track
    # centerline. The rails sit about half a gauge closer to the wall than
    # the distance recorded here.
    # curves is a list of polylines. The default samples lines.Beziers.

    if curves is None:
        curves = track_sample_curves()

    size = float(cfg.get("sector_real_size"))
    distances = []
    located = []
    missed = []
    crossings = 0
    pairs = set()

    for curve in curves:

        previous_id = None

        for point in curve:

            sector_id = get_sector_id_at_position(point)
            if not sector_id:
                missed.append(point)
                previous_id = None
                continue

            sector = Sectors[sector_id]
            candidates = [sector]
            for neighbor_id in sector["neighbors"]:
                if neighbor_id:
                    candidates.append(Sectors[neighbor_id])

            best = size
            px = point[0]
            py = point[1]
            for candidate in candidates:
                for start, end in _unlinked_wall_segments(candidate):
                    dist = _point_segment_distance(px, py, start, end)
                    if dist < best:
                        best = dist

            distances.append(best)
            located.append((best, sector_id, px, py, point[2]))

            if previous_id and previous_id != sector_id:
                other = Sectors.get(previous_id)
                if other is not None and not sectors_share_a_wall(other, sector):
                    # Only a cardinal step can be a cut wall. A stack change
                    # or a diagonal jump is a different gap.
                    if _CARDINAL_SLOT.get(
                        (sector["x"] - other["x"], sector["y"] - other["y"])
                    ) is not None:
                        crossings += 1
                        pairs.add(tuple(sorted((previous_id, sector_id))))

            previous_id = sector_id

    labels = _wall_bin_labels()
    if distances:
        values = np.array(distances, dtype=float)
        histogram = np.histogram(
            values, bins=list(WALL_BIN_EDGES) + [np.inf]
        )[0]
        summary = {
            "min": float(values.min()),
            "p1": float(np.percentile(values, 1)),
            "p5": float(np.percentile(values, 5)),
            "median": float(np.median(values)),
            "mean": float(values.mean()),
            "max": float(values.max()),
            "under": int((values < WALL_COLLISION).sum()),
        }
    else:
        histogram = [0] * len(labels)
        summary = {
            "min": None,
            "p1": None,
            "p5": None,
            "median": None,
            "mean": None,
            "max": None,
            "under": 0,
        }

    located.sort()
    # Two curves often share an endpoint. Keep one row per place so the
    # list is places to visit in Hammer, not repeated samples.
    worst = []
    seen = set()
    for distance, sector_id, px, py, pz in located:
        key = (sector_id, round(px), round(py), round(pz))
        if key in seen:
            continue
        seen.add(key)
        worst.append(
            {
                "distance": distance,
                "sector": sector_id,
                "x": px,
                "y": py,
                "z": pz,
            }
        )
        if len(worst) == WALL_WORST:
            break

    return {
        "count": len(distances),
        "missed": missed,
        "histogram": list(zip(labels, (int(count) for count in histogram))),
        "worst": worst,
        "crossings": crossings,
        "pairs": len(pairs),
        "crossing_pairs": sorted(pairs),
        "corkscrew_breaks": corkscrew_breaks,
        "corkscrew_errors": corkscrew_errors,
        **summary,
    }


def report_wall_clearance(curves=None):

    # Printed after sectors are linked. Same numbers as check_wall_clearance.py.
    stats = measure_wall_clearance(curves)
    if stats["count"] == 0:
        print("Wall clearance: no sampled track points")
        return stats

    print(
        "Wall clearance, track centerline "
        "(rails sit about half a gauge closer):"
    )
    print(
        f"  {stats['count']} points   "
        f"min {stats['min']:.0f}   p1 {stats['p1']:.0f}   "
        f"p5 {stats['p5']:.0f}   median {stats['median']:.0f}   "
        f"mean {stats['mean']:.1f}   max {stats['max']:.0f}"
    )
    print(
        f"  under {WALL_COLLISION}: {stats['under']}"
    )
    print(
        f"  unlinked cardinal crossings: {stats['crossings']} "
        f"({stats['pairs']} sector pairs)"
    )
    for left_id, right_id in stats["crossing_pairs"][:WALL_WORST]:
        print(f"    {left_id}  {right_id}")
    if stats["pairs"] > WALL_WORST:
        print(f"    ... {stats['pairs'] - WALL_WORST} more pairs")
    print(
        f"  corkscrew breaks: {stats['corkscrew_breaks']}   "
        f"errors: {stats['corkscrew_errors']}"
    )
    if stats["missed"]:
        print(f"  outside every sector: {len(stats['missed'])}")
        for point in stats["missed"][:WALL_WORST]:
            print(f"    ({point[0]:.1f}, {point[1]:.1f}, {point[2]:.1f})")
    print(
        "  histogram: "
        + " | ".join(f"{label} {count}" for label, count in stats["histogram"])
    )
    print("  worst:")
    for item in stats["worst"]:
        print(
            f"    {item['distance']:.1f}  {item['sector']}  "
            f"({item['x']:.1f}, {item['y']:.1f}, {item['z']:.1f})"
        )
    return stats


def get_expanded_points(startpoints, offset):
    expanded_points = []

    for x, y, z in startpoints:
        for dx in [-offset, offset]:
            for dy in [-offset, offset]:
                expanded_points.append([x + dx, y + dy, z])

    return startpoints + expanded_points


def sort_points_to_sector_grid_buckets(points, sectors_per_map):

    sector_height_buckets = {}

    for point in points:

        sector_x, sector_y = convert_real_to_sector_xy(point)

        if abs(sector_x + 0.5) > (sectors_per_map / 2):
            continue

        if abs(sector_y + 0.5) > (sectors_per_map / 2):
            continue

        sector_lookup = f"{sector_x}x{sector_y}"

        sector_height_buckets.setdefault(sector_lookup, []).append(
            ((sector_x, sector_y), -point[2])
        )

    # One stable sort per column. heuristic_inserter walked the bucket for
    # every point (higher -z first, ties left in arrival order). sort is
    # stable, so equal heights stay in that same order.
    for bucket in sector_height_buckets.values():
        bucket.sort(key=lambda item: item[1], reverse=True)

    return sector_height_buckets


def build_fit():

    # Takes all points, makes buckets representing new possible sectors, expands and creates sectors as needed.

    sector_minimum_height = cfg.get("sector_minimum_height")
    sector_maximum_height = cfg.get("sector_maximum_height")
    sector_minimum_track_depth = cfg.get("sector_minimum_track_depth")
    sector_snap_grid = cfg.get("sector_snap_grid")
    sector_real_size = cfg.get("sector_real_size")
    sectors_per_map = cfg.get("sectors_per_map")
    sector_minimum_track_to_edge_distance = cfg.get(
        "sector_minimum_track_to_edge_distance"
    )

    points = get_expanded_points(
        lines.get_all_track_points(), sector_minimum_track_to_edge_distance
    )

    def set_current_bounds(point):
        floor = tools.downtomult(
            point - sector_minimum_track_depth,
            sector_snap_grid,
        )

        ceiling = tools.downtomult(floor + sector_minimum_height, sector_snap_grid)

        return floor, ceiling

    sector_height_buckets = sort_points_to_sector_grid_buckets(points, sectors_per_map)
    fitted = list(sector_height_buckets.values())
    fitting = tools.progress("Fitting", len(fitted))

    for fit_index, this_sector_heights_sorted in enumerate(fitted, 1):

        sector_x = this_sector_heights_sorted[0][0][0]
        sector_y = this_sector_heights_sorted[0][0][1]
        current_floor_height, current_ceiling_height = set_current_bounds(
            -this_sector_heights_sorted[0][1]
        )

        for id in range(1, len(this_sector_heights_sorted)):
            next_point_height = -this_sector_heights_sorted[id][1]

            if next_point_height <= (
                current_ceiling_height + sector_minimum_track_depth
            ):
                continue
            else:
                prev_height = -this_sector_heights_sorted[id - 1][1]

            gap = next_point_height - prev_height

            if (
                gap > sector_minimum_height
            ):  # err on the side of subdividing more, but this might not work out

                under_next_sector_floor = math.floor(
                    ((next_point_height - sector_minimum_track_depth))
                    - sector_snap_grid * 2
                )
                maximum_height_from_current_floor = (
                    current_ceiling_height + sector_maximum_height
                )

                cap_height = tools.downtomult(
                    min(under_next_sector_floor, maximum_height_from_current_floor),
                    sector_snap_grid,
                )

                new_sector(
                    sector_x,
                    sector_y,
                    current_floor_height,
                    cap_height,
                )

                current_floor_height, current_ceiling_height = set_current_bounds(
                    next_point_height
                )

        # when there's no points left, make a topmost sector that encapsulates the remainder
        new_sector(
            sector_x,
            sector_y,
            current_floor_height,
            tools.downtomult(
                current_ceiling_height + sector_maximum_height, sector_snap_grid
            ),
        )
        fitting(fit_index)

    fitting.finish()

    tools.stopwatch_click("submodule", "Sectors Built & Fit")


def get_all():
    return Sectors


def build_kdtree_for_sector(sector_data):
    """
    Builds and caches a KDTree (on x, y only) for the 'points' in a sector.
    Attaches it to sector['kdtree'] and sector['kdtree_data'] for lookup.
    """
    if "points" not in sector_data or not sector_data["points"]:
        sector_data["kdtree"] = None
        sector_data["kdtree_data"] = None
        return

    # Build 2D KDTree using x, y only
    points = sector_data["points"]
    xy_coords = [(p[0], p[1]) for p in points]
    tree = KDTree(xy_coords)

    sector_data["kdtree"] = tree
    sector_data["kdtree_data"] = points  # Keep original points to reference index


def assign_points_to_sectors():

    # gives each sector an internal lookup of points in itself + neighbors in a plus-sign shape (connected ones only)
    from collections import defaultdict

    # Step 1: Map points to their specific sector via floor/ceiling lookup
    sector_point_map = defaultdict(list)

    points = lines.get_all_track_points()

    for point in points:
        sector_id = get_sector_id_at_position(point)
        if not sector_id:
            continue  # Shouldn't happen, but safety first
        sector_point_map[sector_id].append(point)

    # Step 2: For each sector, gather its own and neighbor points
    assigning = tools.progress("Assigning points", len(Sectors))
    for assign_index, (sector_id, sector_data) in enumerate(Sectors.items(), 1):
        all_points = list(sector_point_map.get(sector_id, []))

        for neighbor_id in sector_data.get("neighbors", []):
            if neighbor_id and isinstance(neighbor_id, str):
                all_points.extend(sector_point_map.get(neighbor_id, []))

        if not all_points:
            all_points = np.empty((0, 3))

        sector_data["points"] = lines.get_terrain_points_from_sample(all_points)

        build_kdtree_for_sector(sector_data)
        assigning(assign_index)

    assigning.finish()


def find_closest_point_2d(sector, x, y):

    # convert a sector and X/Y pair into the closest track-point in that sector by 2d distance
    """
    Returns the closest 3D point (x, y, z) in the sector to the input x, y.
    Assumes the sector already has its KDTree built.
    """
    if "kdtree" not in sector or sector["kdtree"] is None:
        return None  # No points to compare

    dist, idx = sector["kdtree"].query((x, y))
    return dist, sector["kdtree_data"][idx]


def get(sector_id, default=None):
    return Sectors.get(sector_id, default)


def _diagonal_neighbor_id(sector_data, dx, dy):

    # The diagonal sector is "go sideways, then forward" or the other order.
    # A corkscrew can make those two walks disagree; either linked walk is a
    # real sector touching this corner.
    h_slot = 1 if dx > 0 else 3
    v_slot = 0 if dy > 0 else 2

    for first, second in ((h_slot, v_slot), (v_slot, h_slot)):

        side_id = sector_data["neighbors"][first]
        if not side_id or not isinstance(side_id, str):
            continue

        side = Sectors.get(side_id)
        if not side:
            continue

        diag = side["neighbors"][second]
        if diag and isinstance(diag, str) and diag in Sectors:
            return diag

    return None


def _remember_corner(slots, sector_data, dx, dy, grid_name):

    grid = sector_data["grid"].get(grid_name)
    if not grid:
        return
    size = len(grid)
    x = size - 1 if dx > 0 else 0
    y = size - 1 if dy > 0 else 0
    slots.append((grid, x, y))


def _alias_slots(slots, mode):

    # Point every slot at one list, after writing the merged value into it.
    # Replacing the list (not just the value) is what makes a diagonal corner
    # the same vertex as the three edge-neighbors. Later blurs write [0] and
    # the alias keeps holding.
    if len(slots) < 2:
        return

    values = [grid[x][y][0] for grid, x, y in slots]
    if mode == "highest":
        merged = max(values)
    elif mode == "lowest":
        merged = min(values)
    else:
        merged = sum(values) / len(values)

    grid0, x0, y0 = slots[0]
    grid0[x0][y0][0] = merged
    canonical = grid0[x0][y0]
    for grid, x, y in slots[1:]:
        grid[x][y] = canonical


def share_diagonal_corners():

    # N/E/S/W edge merges already alias the corners of sectors that share an
    # edge. The sector that only touches at the corner still has its own list,
    # and that unmatched vertex is the exposed displacement corner. Gather
    # every sector that meets at the point and alias them.

    names = (
        ("minmap", "highest"),
        ("maxmap", "lowest"),
        ("height", "highest"),
    )
    seen = set()

    for sector_data in Sectors.values():

        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):

            diag_id = _diagonal_neighbor_id(sector_data, dx, dy)
            if not diag_id:
                continue

            pair = (sector_data["id"], diag_id)
            if pair[0] > pair[1]:
                pair = (pair[1], pair[0])
            if pair in seen:
                continue
            seen.add(pair)

            diag = Sectors[diag_id]

            for grid_name, mode in names:

                slots = []
                _remember_corner(slots, sector_data, dx, dy, grid_name)
                _remember_corner(slots, diag, -dx, -dy, grid_name)

                h_slot = 1 if dx > 0 else 3
                v_slot = 0 if dy > 0 else 2
                side_h = sector_data["neighbors"][h_slot]
                side_v = sector_data["neighbors"][v_slot]
                if isinstance(side_h, str) and side_h in Sectors:
                    _remember_corner(slots, Sectors[side_h], -dx, dy, grid_name)
                if isinstance(side_v, str) and side_v in Sectors:
                    _remember_corner(slots, Sectors[side_v], dx, -dy, grid_name)

                _alias_slots(slots, mode)


def merge_edges():

    # having agreed on link status, bind all the edges of the grids to each other
    # roughly, runs through every grid in the 3 different types of grids, seaches for ones that appear in the neighbor lookup, merges info along the shared edge

    for sector_data in Sectors.values():

        grids_to_unify = [
            ["minmap", "highest"],
            ["maxmap", "lowest"],
            ["height", "highest"],
        ]

        for grid_to_unify in grids_to_unify:
            grid = sector_data["grid"].get(grid_to_unify[0])

            if grid is None:
                print(sector_data, "nono")
                continue  # Skip if maps are missing

            size = len(grid)

            for dir_key, idx in {"N": 0, "E": 1, "S": 2, "W": 3}.items():
                neighbor_id = sector_data["neighbors"][idx]
                if not neighbor_id or not isinstance(neighbor_id, str):
                    continue

                neighbor = Sectors.get(neighbor_id)
                if not neighbor:
                    print(neighbor_id, "popo")
                    continue

                neighbor_grid = neighbor["grid"].get(grid_to_unify[0])

                if neighbor_grid is None:
                    continue

                l = [0]
                hook = ()
                if dir_key == "N":
                    hook = (l, [0], l, [-1])

                elif dir_key == "E":
                    hook = ([0], l, [-1], l)

                elif dir_key == "S":
                    hook = (l, [-1], l, [0])

                else:  # dir_key == "W":
                    hook = ([-1], l, [0], l)

                # -1 is the south side 0 is the north side

                for x in range(size):

                    l[0] = x

                    A = neighbor_grid[hook[0][0]][hook[1][0]][0]
                    B = grid[hook[2][0]][hook[3][0]][0]

                    if grid_to_unify[1] == "highest":
                        C = max(A, B)

                    elif grid_to_unify[1] == "lowest":
                        C = min(A, B)

                    elif grid_to_unify[1] == "even":
                        C = (A + B) / 2

                    grid[hook[2][0]][hook[3][0]][0] = C
                    neighbor_grid[hook[0][0]][hook[1][0]] = grid[hook[2][0]][hook[3][0]]

    share_diagonal_corners()

    tools.stopwatch_click("submodule", "Merge edges complete")


def apply_algorithm_to_grid(oldgrid, algorithm, adjust):
    # applies an algorithm input to each square in a grid

    gridsize = len(oldgrid)
    new_grid = tools.blank_list_grid(2, gridsize, 0)

    for y in range(gridsize):
        for x in range(gridsize):
            results = get_nearby_gridsquare_data(x, y, oldgrid, gridsize)
            new_grid[y][x][0] = algorithm(oldgrid[y][x][0], results, adjust)

    return new_grid


def overwrite_grid(oldgrid, newgrid):
    # Takes data from newgrid and carefully replaces data in oldgrid without disturbing the pass-by-reference

    gridsize = len(oldgrid)

    for y in range(gridsize):
        for x in range(gridsize):
            oldgrid[y][x][0] = newgrid[y][x][0]


def get_nearby_gridsquare_data(x, y, grid, gridsize):

    # Gets a 3x3 grid of samples from nearby entries in the grid, excluding empty boxes.
    output = []

    for dy in [-1, 0, 1]:
        for dx in [-1, 0, 1]:
            ny = y + dy
            nx = x + dx
            if 0 <= ny < gridsize and 0 <= nx < gridsize:
                output += [grid[ny][nx][0]]

    return output


def blur_grid(grid_name, iterations, algorithm):

    # has to be in this order so changes propagate between sectors (they share edges)
    for _ in range(iterations):

        for sector_data in Sectors.values():

            grid = sector_data["grid"].get(grid_name)

            if grid is None:
                print(sector_data, "nono")
                continue  # Skip if maps are missing

            # spits out a new (identical but processed) grid - does not edit original
            new_grid = apply_algorithm_to_grid(
                grid, algorithm, cfg.get("noise_grid_max_deviation_adjustment")
            )

            # this preserves the merged edges using Python pass-by-reference lists
            overwrite_grid(grid, new_grid)


def _spread_envelope(grid, step, mode):

    # One Jacobi pass. A high floor (mode "up") raises a neighbor to
    # value - step * cell_distance, and never lowers anything. A low ceiling
    # (mode "down") does the mirror. cell_distance is 1 orthogonally and
    # sqrt(2) on the diagonal, and `step` is slope * node spacing, so both
    # directions move at the same rise/run. Values only move one way, so the
    # iteration cannot oscillate; it stops when a pass changes nothing.
    size = len(grid)
    new_grid = tools.blank_list_grid(2, size, 0)
    changed = False

    for x in range(size):
        for y in range(size):

            current = grid[x][y][0]
            updated = current

            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx = x + dx
                    ny = y + dy
                    if nx < 0 or ny < 0 or nx >= size or ny >= size:
                        continue
                    dist = math.sqrt(2.0) if dx != 0 and dy != 0 else 1.0
                    if mode == "up":
                        candidate = grid[nx][ny][0] - step * dist
                        if candidate > updated:
                            updated = candidate
                    else:
                        candidate = grid[nx][ny][0] + step * dist
                        if candidate < updated:
                            updated = candidate

            if updated != current:
                changed = True
            new_grid[x][y][0] = updated

    return new_grid, changed


def blur_min_max_grids(iterations=None):

    # Spread floor and ceiling limits until the slope between neighbors has
    # settled. `iterations` is an optional safety cap. Leaving it out runs
    # long enough to cross the map; the old fixed 5 passes stopped early and
    # left the rest of a tall transition as a cliff.
    spacing = cfg.get("sector_real_size") / max(cfg.get("noise_grid_per_sector") - 1, 1)
    step = cfg.get("noise_floor_ceiling_spillover_slope") * spacing

    if iterations is None:
        limit = int(cfg.get("noise_grid_per_sector") * max(cfg.get("sectors_per_map"), 1) * 2) + 8
    else:
        limit = max(int(iterations), 0)

    passes = 0
    settled = False

    for _ in range(limit):

        passes += 1
        changed = False

        for sector_data in Sectors.values():

            for name, mode in (("minmap", "up"), ("maxmap", "down")):

                grid = sector_data["grid"].get(name)
                if not grid:
                    continue

                new_grid, did = _spread_envelope(grid, step, mode)
                if did:
                    changed = True
                overwrite_grid(grid, new_grid)

        if not changed:
            settled = True
            break

    if not settled and limit:
        print(
            f"Floor/ceiling spread hit the {limit}-pass cap before the slope settled."
        )

    tools.stopwatch_click("submodule", f"Blur min-max done ({passes} passes)")


def blur_heightmap_grid(announce=True):

    # Wrapper function for using blur_grid on the heightmap. The average is
    # not clamped here; heightmap.relax_heightmaps clamps after every pass.

    def cut_down_outliers(base, list, adjust):

        weight = 3  # must be an integer greater than 0
        total = base * weight

        # means no division by 0 AND value is weighted towards the base
        for entry in list:
            total += entry

        count = weight + len(list)

        return total / count

    blur_grid("height", 1, cut_down_outliers)

    if announce:
        tools.stopwatch_click("submodule", "Smoothed heightmap")


def distance_to_line(pos, sector_data=None):

    # Takes a position and an optional sector (if you know what sector it is already) and spits out the distance to the nearest track-point.

    if sector_data is None:
        sector_id = get_sector_id_at_position(pos)
        if sector_id in Sectors:
            sector_data = Sectors[sector_id]
        else:
            # print(pos, sector_id, "failed!")
            return 9999999999, [100000, 10000, 100000]

    KDTree = sector_data["kdtree"]
    Points = sector_data["points"]

    if KDTree == None:
        # rint("Bad KDTree!")
        return 9999999999, [100000, 10000, 100000]

    Shortest, idx = KDTree.query([pos[0], pos[1]])
    Pos = Points[idx]

    return Shortest, Pos


def _nearest_track_distance():

    # One 3D tree of the track samples as they stand right now. Ground hints
    # are still staged at this point in the build, so they are not in the tree.
    # Stacked track stays out of each other's way because the distance is 3D.
    # encode_lines uses a single far point when the map has no track. That is
    # not a rail; both sides tie and the second option wins, same as before.

    points = []
    for point in lines.get_all_track_points():
        points.append((float(point[0]), float(point[1]), float(point[2])))

    if not points or points == [(100000.0, 100000.0, 100000.0)]:

        def tied(_pos):
            return 0.0

        return tied

    tree = cKDTree(points)

    def distance(pos):
        found, _idx = tree.query((float(pos[0]), float(pos[1]), float(pos[2])))
        return float(found)

    return distance


def collapse_quantum_switchstands():

    # Roughly: takes the encoded 2-option switch stand entities and overwrites itself with whichever one is farthest from the rails.
    # Good way of finding unobstructed stand locations.

    Entities = vmfpy.get_entities()
    distance_to_track = _nearest_track_distance()

    for ID in range(len(Entities)):

        Ent = Entities[ID]

        try:
            if Ent[0][0] == "collapse":
                Collapse = 1
            else:
                Collapse = 0
        except:
            Collapse = 0

        if Collapse:

            FirstDistance = distance_to_track(Ent[0][1])
            SecondDistance = distance_to_track(Ent[0][2])

            if FirstDistance > SecondDistance:
                Entities[ID] = Ent[1]
            else:
                Entities[ID] = Ent[2]
