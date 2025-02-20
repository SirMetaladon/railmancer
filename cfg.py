import tools, random


def initialize(path: str):

    global CFG

    CFG = tools.import_json(path)

    try:
        CFG["Biomes"]
    except:
        # no biomes? crash on purpose, you need that!
        print("Unable to get Biomes from CFG!")
        print(Exception)

    max_mapsize = 32768

    # this is the default CFG data, format label, default, min, max
    Expecting = [
        ["sector_size", 4080, 16, max_mapsize],
        ["Noise_Size", 25, 1, 1000],
        ["line_maximum_poll_point_distance", 25, 1, 1000],
        ["Disps_Per_Sector", 3, 1, 50],
        ["sector_snap_grid", 16, 1, 128],
        ["sector_minimum_wall_height", 1824, 0, max_mapsize],
        ["sector_minimum_track_depth", 128, 0, max_mapsize],
        ["sector_minimum_track_clearance", 512, 0, max_mapsize],
    ]

    # need a mechanism in here for double checking the following:
    # Is sector size a multiple of snap size?
    # Is wall height a multiple of snap size?
    # Is Displacements per Sector an integer?

    for Entry in Expecting:

        CFG[Entry[0]] = min(max(CFG.get(Entry[0], Entry[1]), Entry[2]), Entry[3])

    for Biome in CFG["Biomes"].values():
        Biome["terrain"]["seed"] = random.randint(0, 100)

    # this must be an even number for alignment to work
    CFG["sectors_per_map"] = int(max_mapsize / CFG["sector_size"])
    CFG["sector_minimum_cube_gap"] = (
        CFG["sector_minimum_track_clearance"] + CFG["sector_minimum_track_depth"]
    ) / CFG["sector_snap_grid"]

    return CFG


def get(path):
    return CFG[path]
