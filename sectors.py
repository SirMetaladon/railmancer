import random, tools


def within_sector_height(sector_id, height):

    return (
        height >= Sectors[sector_id][0]["floor"]
        and height <= Sectors[sector_id][0]["ceiling"]
    )


def get_sector_id(x, y, height):

    sector_list = sector_lookup_grid.get(f"{x}x{y}", False)

    if sector_list == False:
        return False

    for possible_sector in sector_list:

        if within_sector_height(possible_sector, height):

            return possible_sector

    return False


def get_connected_sector_data(x, y, height):

    sector_id = get_sector_id(x, y, height + 21)

    if sector_id is False:
        return False

    sector_data = Sectors[sector_id][0]

    if abs(height - sector_data["floor"]) <= 21:
        # it may be prudent to add more checks here for more absurd (low-height) blocks, but it's low priority (just don't make blocks less than 21 high?)
        # print(x, y, sector_data)
        return sector_data

    else:
        return False


def new_sector(x, y, floor, ceiling):

    sector_lookup = f"{x}x{y}"

    sector_id = f"{sector_lookup}x{floor}"

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
            "floor": floor,
            "ceiling": ceiling,
            "minmap": [],
            "maxmap": [],
            "heightmap": [],
        }
    ]


def sector_square(data):

    xmin, xmax, ymin, ymax, bottom, top = data

    # idiot insurance
    floor = min(bottom, top)
    ceiling = max(bottom, top)

    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            new_sector(
                x=x,
                y=y,
                floor=floor,
                ceiling=ceiling,
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


def build_sectors(build_method, data):

    global Sectors, sector_lookup_grid

    try:
        return Sectors
    except:
        Sectors = {}
        sector_lookup_grid = {}

    if build_method == "sector_path_random":

        sector_path_random(data)

    elif build_method == "sector_square":

        sector_square(data)

    for Sector in Sectors.items():

        sector_id = Sector[0]
        XCoord = Sector[1][0]["x"]
        YCoord = Sector[1][0]["y"]
        FloorHeight = Sector[1][0]["floor"]

        Sectors[sector_id] += [
            get_connected_sector_data(XCoord, YCoord + 1, FloorHeight)
        ]
        Sectors[sector_id] += [
            get_connected_sector_data(XCoord + 1, YCoord, FloorHeight)
        ]
        Sectors[sector_id] += [
            get_connected_sector_data(XCoord, YCoord - 1, FloorHeight)
        ]
        Sectors[sector_id] += [
            get_connected_sector_data(XCoord - 1, YCoord, FloorHeight)
        ]

    return Sectors


"""def build_blocks_square(xmin=-4, xmax=3, ymin=-4, ymax=3, bottom=0, top=514):

    # idiot insurance
    floor = min(bottom, top)
    ceiling = max(bottom, top)

    grid = [
        [x, y, floor, ceiling]
        for x in range(xmin, xmax + 1)
        for y in range(ymin, ymax + 1)
    ]
    return grid
"""
