from railmancer import tools
import random

# This file handles all interactions between Railmancer and the Configuration file, sets defaults, and interpets information.


def initialize(path: str):

    global CFG

    CFG = tools.import_json(path)

    try:
        CFG["Biomes"]
    except:
        # no biomes? crash on purpose, you need that!
        print("Unable to get Biomes from CFG!")
        print(Exception)

    max_mapsize = 32768  # hardcoded source limit

    # this is the default CFG data, format label, default, min, max
    Expecting = [
        ["sector_real_size", 4080, 16, max_mapsize],
        ["noise_grid_per_sector", 25, 1, 1000],
        ["line_maximum_poll_point_distance", 25, 1, 1000],
        ["sector_displacement_subdivision_rate", 3, 1, 50],
        ["sector_snap_grid", 16, 1, 128],
        ["sector_minimum_wall_height", 1824, 0, max_mapsize],
        ["sector_minimum_track_depth", 128, 0, max_mapsize],
        ["sector_minimum_vertical_track_clearance", 512, 0, max_mapsize],
        ["noise_floor_ceiling_spillover_slope", 2, 0, 100],
        ["trackhammer_minimum_allowed_distance_from_edge_of_map", 1000, 0, max_mapsize],
    ]

    # need a mechanism in here for double checking the following:
    # Is sector size a multiple of snap size?
    # Is wall height a multiple of snap size?
    # Is Displacements per Sector an integer?

    for Entry in Expecting:

        CFG[Entry[0]] = int(min(max(CFG.get(Entry[0], Entry[1]), Entry[2]), Entry[3]))

    for Biome in CFG["Biomes"].values():
        Biome["terrain"]["seed"] = random.randint(0, 100)

    CFG["trackhammer_border"] = (
        max_mapsize / 2 - CFG["trackhammer_minimum_allowed_distance_from_edge_of_map"]
    )  # to make calculations easier

    # this must be an even number for alignment to work
    CFG["sectors_per_map"] = int(max_mapsize / CFG["sector_real_size"])
    CFG["sector_minimum_cube_gap"] = (
        CFG["sector_minimum_vertical_track_clearance"]
        + CFG["sector_minimum_track_depth"]
    ) / CFG["sector_snap_grid"]

    # adjust can be calculated from CFG "slope of terrain away from hard edges" + the size of a gridsquare.
    # Slope is (Sector size / number of gridsquares) * CFG Slope (the quantity up/down)
    # terrain rabbithole

    # Nuts to that, let's hardcode it again. But smarter.
    decay_slope = 2
    # there is a universe where we want to change this based on terrain NIGHTMARE NIGHTMARE NIGHTMARE
    CFG["noise_grid_max_deviation_adjustment"] = CFG[
        "noise_floor_ceiling_spillover_slope"
    ] * (CFG["sector_real_size"] / CFG["noise_grid_per_sector"])
    return CFG


def get(path):
    return CFG[path]
