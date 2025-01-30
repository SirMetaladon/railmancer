"""def encode_sector(X, Y):

    return 


def get_sector(X, Y):

    return Sectors.get(encode_sector(X, Y), False)
    

    def probe_sector(x, y):

        Sector = get_sector(x, y)

        if Sector is False:
            return False

        else:
            return Sector[0]"""


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

        if within_sector_height(sector_list[0], height):

            return possible_sector

    return False


def get_connected_sector_data(x, y, height):

    sector_id = get_sector_id(x, y, height)

    if sector_id is False:
        return False

    sector_data = Sectors[sector_id][0]

    if abs(height - sector_data["floor"]) > 21:
        # it may be prudent to add more checks here for more absurd (low-height) blocks, but it's low priority (just don't make blocks less than 21 high?)
        return sector_data


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


def build_sectors(Blocks):

    global Sectors, sector_lookup_grid

    try:
        return Sectors
    except:
        Sectors = {}
        sector_lookup_grid = {}

    for Entry in Blocks:

        x, y, floor, ceiling = Entry

        new_sector(x=x, y=y, floor=floor, ceiling=ceiling)

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
