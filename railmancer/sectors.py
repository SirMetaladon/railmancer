import math, random
from railmancer import tools, cfg, lines


def initialize():
    global Sectors, sector_lookup_grid

    try:
        return Sectors
    except:
        Sectors = {}
        sector_lookup_grid = {}


def within_sector_height(sector_id, floor, ceiling):

    floor_limit = max(floor, Sectors[sector_id][0]["floor"])
    ceiling_limit = min(ceiling, Sectors[sector_id][0]["ceiling"])

    return (ceiling_limit - floor_limit) >= cfg.get("sector_minimum_cube_gap")


def get_connected_sector_data(x, y, floor, ceiling):

    sector_list = sector_lookup_grid.get(f"{x}x{y}", False)

    if sector_list == False:
        return False

    sector_id = ""

    for possible_sector in sector_list:

        if within_sector_height(possible_sector, floor, ceiling):

            sector_id = possible_sector
            break

    else:
        return False

    sector_data = Sectors[sector_id][0]

    # if abs(height - sector_data["floor"]) <= 21:
    # it may be prudent to add more checks here for more absurd (low-height) blocks, but it's low priority (just don't make blocks less than 21 high?)
    # print(x, y, sector_data)
    return sector_data

    """else:
        return False"""


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

    Sectors[sector_id] = [
        {
            "id": sector_id,
            "x": x,
            "y": y,
            "floor": floor_real,
            "ceiling": ceiling_real,
            "local_lines": [],
            "relevant_lines": [],
            "minmap": [],
            "maxmap": [],
            "heightmap": [],
        }
    ]


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


def stitch():  # takes all sectors, finds nearby sectors, and adds them to existing sectors effectively allowing each sector to reference it's neighbors

    for Sector in Sectors.items():

        sector_id = Sector[0]
        XCoord = Sector[1][0]["x"]
        YCoord = Sector[1][0]["y"]
        FloorHeight = Sector[1][0]["floor"]
        CeilingHeight = Sector[1][0]["ceiling"]

        Sectors[sector_id] += [
            get_connected_sector_data(XCoord, YCoord + 1, FloorHeight, CeilingHeight)
        ]
        Sectors[sector_id] += [
            get_connected_sector_data(XCoord + 1, YCoord, FloorHeight, CeilingHeight)
        ]
        Sectors[sector_id] += [
            get_connected_sector_data(XCoord, YCoord - 1, FloorHeight, CeilingHeight)
        ]
        Sectors[sector_id] += [
            get_connected_sector_data(XCoord - 1, YCoord, FloorHeight, CeilingHeight)
        ]


def build_fit():

    sector_minimum_wall_height = cfg.get("sector_minimum_wall_height")
    sector_minimum_track_depth = cfg.get("sector_minimum_track_depth")
    sector_minimum_vertical_track_clearance = cfg.get(
        "sector_minimum_vertical_track_clearance"
    )
    sector_snap_grid = cfg.get("sector_snap_grid")
    sector_size = cfg.get("sector_size")
    sectors_per_map = cfg.get("sectors_per_map")
    sector_minimum_track_to_edge_distance = cfg.get(
        "sector_minimum_track_to_edge_distance"
    )

    points = lines.get_sampled_points()

    points_extended = []

    for point in points:

        x, y, z = point

        points_extended += [
            [
                x + sector_minimum_track_to_edge_distance,
                y + sector_minimum_track_to_edge_distance,
                z,
            ]
        ]
        points_extended += [
            [
                x - sector_minimum_track_to_edge_distance,
                y + sector_minimum_track_to_edge_distance,
                z,
            ]
        ]
        points_extended += [
            [
                x + sector_minimum_track_to_edge_distance,
                y - sector_minimum_track_to_edge_distance,
                z,
            ]
        ]
        points_extended += [
            [
                x - sector_minimum_track_to_edge_distance,
                y - sector_minimum_track_to_edge_distance,
                z,
            ]
        ]

    points += points_extended

    sector_height_buckets = {}

    for point in points:

        sector_x = math.floor(point[0] / sector_size)
        sector_y = math.floor(point[1] / sector_size)

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
