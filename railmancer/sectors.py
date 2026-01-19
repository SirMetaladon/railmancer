import math, random
from railmancer import tools, cfg, lines, vmfpy, terrain
from scipy.spatial import KDTree
import numpy as np

# Handles the creation and management of Sector objects, how they connect to each other, things related to stitching them together, and anything that takes sector objects instead of just raw grids.


def initialize():

    # Have to run this initially to get the Sectors dictionary up and running.
    global Sectors, sector_lookup_grid

    try:
        return Sectors
    except:
        Sectors = {}
        sector_lookup_grid = {}


def sectors_are_connected(first_sector, second_sector):

    # this algorithm tells a sector if it is capable of connecting to another sector. Rules can be arbitrary.

    floor_limit = max(first_sector["floor"], second_sector["floor"])
    ceiling_limit = min(first_sector["ceiling"], second_sector["ceiling"])

    # add a check in here for "is there a sector directly above me that is connected in a roundabout way"

    return (ceiling_limit - floor_limit) >= cfg.get("sector_minimum_cube_gap")


def get_sector_relative_to_this_sector(sector_data, nudge):

    # special function that scans nearby connected and returns them (for a certain height)

    sector_list = sector_lookup_grid.get(
        f"{sector_data["x"]+nudge[0]}x{sector_data["y"]+nudge[1]}", False
    )

    if sector_list is False:
        return False

    for possible_sector_id in sector_list:

        if sectors_are_connected(sector_data, Sectors[possible_sector_id]):

            return possible_sector_id

    # if no sectors found or none were within height range
    return False


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

    # creates a new sector object at the x,y sector-grid coordinates using the correct heights.

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

    # box of sectors for testing

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

    # randomly moving path of sectors that cannot intersect itself

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

    # wrapper for creating sectors not from linedata

    if build_method == "sector_path_random":

        sector_path_random(data)

    elif build_method == "sector_square":

        sector_square(data)


def link():

    # takes all sectors, finds nearby sectors, and adds them to a list of neighbors, then checks those lists for consistiency

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


def build_fit():

    # Takes all points, makes buckets representing new possible sectors, expands and creates sectors as needed.

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
    for sector_id, sector_data in Sectors.items():
        all_points = list(sector_point_map.get(sector_id, []))

        for neighbor_id in sector_data.get("neighbors", []):
            if neighbor_id and isinstance(neighbor_id, str):
                all_points.extend(sector_point_map.get(neighbor_id, []))

        if not all_points:
            all_points = np.empty((0, 3))

        sector_data["points"] = lines.get_terrain_points_from_sample(all_points)

        build_kdtree_for_sector(sector_data)


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


def blur_min_max_grids():

    # Wrapper function for using blur_grid on the min and max grids to propagate ceilings and floors into adjacent sectors.

    def raise_floor(base, list, adjust):

        # take all entries and find the highest
        numpy_list = np.array(list)
        highest = max(numpy_list)

        return max(highest - adjust, base)

    blur_grid("minmap", 35, raise_floor)

    def lower_ceiling(base, list, adjust):

        # take all entries and find the lowest
        numpy_list = np.array(list)
        highest = min(numpy_list)

        return min(highest + adjust, base)

    blur_grid("maxmap", 35, lower_ceiling)


def blur_heightmap_grid():

    # Wrapper function for using blur_grid on the heightmap.

    def cut_down_outliers(base, list, adjust):

        weight = 3  # must be an integer greater than 0
        total = base * weight

        # means no division by 0 AND value is weighted towards the base
        for entry in list:
            total += entry

        count = weight + len(list)

        return total / count

    blur_grid("height", 1, cut_down_outliers)


def distance_to_line(pos, sector_data=None):

    # Takes a position and an optional sector (if you know what sector it is already) and spits out the distance to the nearest track-point.

    if sector_data is None:
        sector_data = Sectors[get_sector_id_at_position(pos)]

    KDTree = sector_data["kdtree"]
    Points = sector_data["points"]

    if KDTree == None:
        # rint("Bad KDTree!")
        return 9999999999, [100000, 10000, 100000]

    Shortest, idx = KDTree.query([pos[0], pos[1]])
    Pos = Points[idx]

    return Shortest, Pos


def collapse_quantum_switchstands():

    # Roughly: takes the encoded 2-option switch stand entities and overwrites itself with whichever one is farthest from the rails.
    # Good way of finding unobstructed stand locations.

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
