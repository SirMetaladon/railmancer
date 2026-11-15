from railmancer import tools
import random, math

# This file handles all interactions between Railmancer and the Configuration file, sets defaults, and interpets information.
CFG: dict = {}


def initialize(path: str):

    global CFG

    CFG = tools.import_json(path)

    try:
        CFG["Biomes"]
    except:
        # no biomes? crash on purpose, you need that!
        print("Unable to get Biomes from CFG!")
        print(Exception)

    # hardcoded source limit
    CFG["max_mapsize"] = 32768

    # this is the default CFG data, format label, default, min, max
    Expecting = [
        ["sector_real_size", 4080, 16, CFG["max_mapsize"]],
        ["noise_grid_per_sector", 25, 1, 1000],
        ["line_maximum_poll_point_distance", 25, 1, 1000],
        ["sector_displacement_subdivision_rate", 3, 1, 50],
        ["sector_snap_grid", 16, 1, 128],
        ["sector_minimum_height", 1824, 0, CFG["max_mapsize"]],
        ["sector_maximum_height", 4000, 0, CFG["max_mapsize"]],
        ["sector_minimum_track_depth", 128, 0, CFG["max_mapsize"]],
        ["noise_floor_ceiling_spillover_slope", 2, 0, 100],
        [
            "trackhammer_minimum_allowed_distance_from_edge_of_map",
            1000,
            0,
            CFG["max_mapsize"],
        ],
        ["trackhammer_block_standoff_distance", 1, 99999, 3000],
        ["trackhammer_block_size_horizontal", 1, 6000, 2000],
    ]

    # Integers and floats are clamped separately so a 1.5 does not get truncated.
    TrackLimits = [
        ["trackhammer_attempt_limit", 250000, 1, 100000000, True],
        ["trackhammer_fit_run_length", 1, 0, 1, True],
    ]

    # need a mechanism in here for double checking the following:
    # Is sector size a multiple of snap size?
    # Is wall height a multiple of snap size?
    # Is Displacements per Sector an integer?

    for Entry in Expecting:

        CFG[Entry[0]] = int(min(max(CFG.get(Entry[0], Entry[1]), Entry[2]), Entry[3]))

    for Entry in TrackLimits:

        name, default, lo, hi, as_int = Entry
        try:
            value = float(CFG.get(name, default))
        except (TypeError, ValueError):
            value = float(default)
        value = min(max(value, lo), hi)
        CFG[name] = int(value) if as_int else value

    # "layers" is the 3-D on/off block grid. "height" stores one absolute
    # rail height per horizontal cell. Anything else falls back to layers
    # so a typo cannot silently change a map.
    block_mode = str(CFG.get("trackhammer_block_mode", "layers")).strip().lower()
    CFG["trackhammer_block_mode"] = (
        block_mode if block_mode in ("layers", "height") else "height"
    )

    # Height mode only. "down" keeps the lowest rail in the cell and requires
    # the next track to pass at least trackhammer_height_clearance underneath it.
    height_direction = (
        str(CFG.get("trackhammer_height_direction", "up")).strip().lower()
    )
    CFG["trackhammer_height_direction"] = (
        height_direction if height_direction in ("up", "down") else "up"
    )

    # Exact vertical gap for height mode, in map units. Defaults to one
    # sector_minimum_height (1200 in the shipped config). That is the same
    # floor-to-ceiling the terrain sectors already use, and it replaces the
    # layers-mode gap of two block layers (2 * sector_minimum_height * 1.05,
    # about 2520) with a distance the next rail can clear exactly.
    try:
        clearance = float(
            CFG.get("trackhammer_height_clearance", CFG["sector_minimum_height"])
        )
    except (TypeError, ValueError):
        clearance = float(CFG["sector_minimum_height"])
    CFG["trackhammer_height_clearance"] = int(
        min(max(clearance, 0), CFG["max_mapsize"])
    )

    CFG["sector_real_size"] = int(math.floor(CFG["sector_real_size"] / 16) * 16)
    for Biome in CFG["Biomes"].values():
        Biome["terrain"]["seed"] = random.randint(0, 100)

        Biome["terrain"]["maximum_models_per_sector"] = int(
            (Biome["terrain"]["maximum_models_per_1kx1k"] / (1000 * 1000))
            * (CFG["sector_real_size"] * CFG["sector_real_size"])
        )

        Biome["terrain"]["model_minimum_distance"] = Biome["terrain"].get(
            "model_minimum_distance", 110
        )

    CFG["trackhammer_border"] = (
        CFG["max_mapsize"] / 2
        - CFG["trackhammer_minimum_allowed_distance_from_edge_of_map"]
    )  # to make calculations easier

    # this must be an even number for alignment to work
    CFG["sectors_per_map"] = int(CFG["max_mapsize"] / CFG["sector_real_size"])

    # adjust can be calculated from CFG "slope of terrain away from hard edges" + the size of a gridsquare.
    # Slope is (Sector size / number of gridsquares) * CFG Slope (the quantity up/down)
    # terrain rabbithole

    # Nuts to that, let's hardcode it again. But smarter.
    decay_slope = 2
    # there is a universe where we want to change this based on terrain NIGHTMARE NIGHTMARE NIGHTMARE
    CFG["noise_grid_max_deviation_adjustment"] = CFG[
        "noise_floor_ceiling_spillover_slope"
    ] * (CFG["sector_real_size"] / CFG["noise_grid_per_sector"])

    tools.stopwatch_click("submodule", "CFG initialized")

    return CFG


def get(path):

    return CFG[path]
