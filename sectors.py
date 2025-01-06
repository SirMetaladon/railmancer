def encode_sector(X, Y):

    return str(X) + "x" + str(Y)


def get_sector(X, Y):

    return Sectors.get(encode_sector(X, Y), False)


def build_sectors(Blocks):

    global Sectors

    try:
        return Sectors
    except:
        Sectors = {}

    for Entry in Blocks:
        Sectors[encode_sector(Entry[0], Entry[1])] = [(Entry[2], Entry[3])]

    # puts in 4 height values to tell you if nearby sectors are filled too
    # think of it as "is there a wall in this direction, and if so how high is it's floor"

    def probe_sector(x, y):

        Sector = get_sector(x, y)

        if Sector is False:
            return False

        else:
            return Sector[0]

    for Sector in Sectors:

        XCoord = int(Sector.split("x")[0])
        YCoord = int(Sector.split("x")[1])

        Sectors[Sector] += [probe_sector(XCoord + 1, YCoord)]
        Sectors[Sector] += [probe_sector(XCoord, YCoord - 1)]
        Sectors[Sector] += [probe_sector(XCoord - 1, YCoord)]
        Sectors[Sector] += [probe_sector(XCoord, YCoord + 1)]

    return Sectors
