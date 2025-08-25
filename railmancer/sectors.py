import math, random
from railmancer import tools, cfg, lines, vmfpy, terrain
from scipy.spatial import KDTree
import numpy as np


def initialize():
    global Sectors, sector_lookup_grid

    try:
        return Sectors
    except:
        Sectors = {}
        sector_lookup_grid = {}


def sectors_are_connected(sector_id, floor, ceiling):

    floor_limit = max(floor, Sectors[sector_id]["floor"])
    ceiling_limit = min(ceiling, Sectors[sector_id]["ceiling"])

    return (ceiling_limit - floor_limit) >= cfg.get("sector_minimum_cube_gap")


def get_sector_id_near_height_connected(x, y, floor, ceiling):

    sector_list = sector_lookup_grid.get(f"{x}x{y}", False)

    if sector_list is False:
        return False

    for possible_sector in sector_list:

        if sectors_are_connected(possible_sector, floor, ceiling):

            return possible_sector

    # if no sectors found or none were within height range
    return False


def convert_real_to_sector_xy(position):

    # sector x/y are integers relative to the overall grid (-3 to 4)
    # virtual x/y are floats fractions within the sector (0 to 1)
    # noise x/y are integers related to points within the sector (0 to span-1)

    real_x, real_y, _ = position

    sector_x = math.floor(real_x / cfg.get("sector_real_size"))
    sector_y = math.floor(real_y / cfg.get("sector_real_size"))
    return sector_x, sector_y


def get_sector_id_at_position(position):

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

    floor_real = min(floor, ceiling)
    ceiling_real = max(floor, ceiling)

    sector_lookup = f"{x}x{y}"

    sector_id = f"{sector_lookup}x{floor_real}"

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


def sector_square(data):

    xmin, xmax, ymin, ymax, bottom, top = data

    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            new_sector(
                x=x,
                y=y,
                floor=top,
                ceiling=bottom,
            )


def sector_path_random(data):

    x_current, y_current, count, block_height, step_height = data

    def code(x, y):
        return f"{x}|{y}"

    encoding = {code(x_current, y_current): [0]}
    new_sector(x=x_current, y=y_current, floor=0, ceiling=block_height)

    for current_height in range(count):
        block_move_options = tools.quadnudge((x_current, y_current), 1)
        random.shuffle(block_move_options)

        done = False

        while block_move_options:
            Pick = block_move_options.pop()
            x_new, y_new = Pick

            if x_new < -4 or x_new > 3 or y_new < -4 or y_new > 3:
                continue

            new_height = (current_height + 1) * step_height

            Sector = code(x_new, y_new)
            if encoding.get(Sector, [-block_height])[-1] + block_height > new_height:
                continue

            tools.blind_add(encoding, Sector, new_height)

            new_sector(
                x=x_new,
                y=y_new,
                floor=new_height,
                ceiling=new_height + block_height,
            )

            x_current, y_current = x_new, y_new

            done = True
            break

        if not done:
            break


def build_manual(build_method, data):

    if build_method == "sector_path_random":

        sector_path_random(data)

    elif build_method == "sector_square":

        sector_square(data)


def link():  # takes all sectors, finds nearby sectors, and adds them to a list of neighbors, then checks those lists for consistiency

    # initially add neighbors
    for Sector_Data in Sectors.values():

        XGrid = Sector_Data["x"]
        YGrid = Sector_Data["y"]
        ZFloor = Sector_Data["floor"]
        ZCeiling = Sector_Data["ceiling"]

        Sector_Data["neighbors"] += [
            get_sector_id_near_height_connected(XGrid, YGrid + 1, ZFloor, ZCeiling),
            get_sector_id_near_height_connected(XGrid + 1, YGrid, ZFloor, ZCeiling),
            get_sector_id_near_height_connected(XGrid, YGrid - 1, ZFloor, ZCeiling),
            get_sector_id_near_height_connected(XGrid - 1, YGrid, ZFloor, ZCeiling),
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


def build_fit():

    sector_minimum_wall_height = cfg.get("sector_minimum_wall_height")
    sector_minimum_track_depth = cfg.get("sector_minimum_track_depth")
    sector_minimum_vertical_track_clearance = cfg.get(
        "sector_minimum_vertical_track_clearance"
    )
    sector_snap_grid = cfg.get("sector_snap_grid")
    sector_real_size = cfg.get("sector_real_size")
    sectors_per_map = cfg.get("sectors_per_map")
    sector_minimum_track_to_edge_distance = cfg.get(
        "sector_minimum_track_to_edge_distance"
    )

    def get_expanded_points(startpoints, offset):
        expanded_points = []

        for x, y, z in startpoints:
            for dx in [-offset, offset]:
                for dy in [-offset, offset]:
                    expanded_points.append([x + dx, y + dy, z])

        return startpoints + expanded_points

    points = get_expanded_points(
        lines.get_all_track_points(), sector_minimum_track_to_edge_distance
    )

    sector_height_buckets = {}

    for point in points:

        sector_x, sector_y = convert_real_to_sector_xy(point)

        if abs(sector_x + 0.5) > (sectors_per_map / 2):
            continue

        if abs(sector_y + 0.5) > (sectors_per_map / 2):
            continue

        sector_lookup = f"{sector_x}x{sector_y}"

        if sector_height_buckets.get(sector_lookup, False):
            tools.heuristic_inserter(
                sector_height_buckets[sector_lookup], ((sector_x, sector_y), -point[2])
            )
        else:
            sector_height_buckets[sector_lookup] = [((sector_x, sector_y), -point[2])]

    for sorted_heights in sector_height_buckets.values():

        floor = -sorted_heights[0][1] - sector_minimum_track_depth

        ceiling = (
            floor + sector_minimum_wall_height - sector_minimum_vertical_track_clearance
        )

        for id in range(1, len(sorted_heights)):
            height = -sorted_heights[id][1]

            if height <= ceiling:
                continue

            prev_height = -sorted_heights[id - 1][1]

            if (height - prev_height) > (
                sector_minimum_vertical_track_clearance + sector_minimum_track_depth
            ):
                new_sector(
                    x=sorted_heights[0][0][0],
                    y=sorted_heights[0][0][1],
                    floor=math.floor(floor / sector_snap_grid),
                    ceiling=math.floor(
                        ((height - sector_minimum_track_depth) / sector_snap_grid) - 2
                    ),
                )

                floor = height - sector_minimum_track_depth
                ceiling = (
                    floor
                    + sector_minimum_wall_height
                    - sector_minimum_vertical_track_clearance
                )

            else:

                ceiling = height

        new_sector(
            x=sorted_heights[0][0][0],
            y=sorted_heights[0][0][1],
            floor=math.floor(floor / sector_snap_grid),
            ceiling=math.floor(
                (ceiling + sector_minimum_vertical_track_clearance) / sector_snap_grid
            ),
        )


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
    from collections import defaultdict

    # Step 1: Map points to their specific sector via floor/ceiling lookup
    sector_point_map = defaultdict(list)

    points = lines.get_terrain_track_points()

    for point in points:
        sector_id = get_sector_id_at_position(point)
        if not sector_id:
            continue  # Shouldn't happen, but safety first
        sector_point_map[sector_id].append(point)

    # Step 2: For each sector, gather its own and neighbor points
    for sector_id, sector_data in Sectors.items():
        all_points = list(sector_point_map.get(sector_id, []))

        for neighbor_id in sector_data.get("neighbors", []):
            if neighbor_id and isinstance(neighbor_id, str):
                all_points.extend(sector_point_map.get(neighbor_id, []))

        sector_data["points"] = all_points

        build_kdtree_for_sector(sector_data)


def find_closest_point_2d(sector, x, y):
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


def merge_edges():

    # having agreed on link status, bind all the edges of the grids to each other

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

                elif dir_key == "W":
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


def blur_grids():

    for num in range(3):

        for sector_data in Sectors.values():

            grids_to_unify = [
                ["minmap", "highest"],
                ["maxmap", "lowest"],
                # ["height", "even"],
            ]

            for grid_to_unify in grids_to_unify:
                grid = sector_data["grid"].get(grid_to_unify[0])

                if grid is None:
                    print(sector_data, "nono")
                    continue  # Skip if maps are missing

                height = len(grid)

                if grid_to_unify[1] == "even":

                    for y in range(height):
                        for x in range(height):
                            total = 0.0
                            count = 0

                            for dy in [-1, 0, 1]:
                                for dx in [-1, 0, 1]:
                                    ny = y + dy
                                    nx = x + dx
                                    if 0 <= ny < height and 0 <= nx < height:
                                        total += grid[ny][nx][0]
                                        count += 1

                            grid[y][x][0] = total / count if count else grid[y][x][0]

                elif grid_to_unify[1] == "highest":

                    for y in range(height):
                        for x in range(height):
                            highest = -10000000

                            for dy in [-1, 0, 1]:
                                for dx in [-1, 0, 1]:
                                    ny = y + dy
                                    nx = x + dx
                                    if 0 <= ny < height and 0 <= nx < height:
                                        highest = max(highest, grid[ny][nx][0])

                            grid[y][x][0] = max(highest - 150, grid[y][x][0])

                elif grid_to_unify[1] == "lowest":

                    for y in range(height):
                        for x in range(height):
                            highest = 10000000

                            for dy in [-1, 0, 1]:
                                for dx in [-1, 0, 1]:
                                    ny = y + dy
                                    nx = x + dx
                                    if 0 <= ny < height and 0 <= nx < height:
                                        highest = min(highest, grid[ny][nx][0])

                            grid[y][x][0] = min(highest + 150, grid[y][x][0])


def distance_to_line(pos, sector_data=None):

    if sector_data is None:
        sector_data = Sectors[get_sector_id_at_position(pos)]

    KDTree = sector_data["kdtree"]
    Points = sector_data["points"]

    if KDTree == None:
        return 9999999999, [100000, 10000, 100000]

    Shortest, idx = KDTree.query([pos[0], pos[1]])
    Pos = Points[idx]

    return Shortest, Pos


def collapse_quantum_switchstands():

    Entities = vmfpy.get_entities()

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

            FirstDistance, _ = distance_to_line(Ent[0][1])
            SecondDistance, _ = distance_to_line(Ent[0][2])

            if FirstDistance > SecondDistance:
                Entities[ID] = Ent[1]
            else:
                Entities[ID] = Ent[2]
