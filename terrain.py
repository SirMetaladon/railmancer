import random, tools


def configuration(path: str):

    global CFG

    CFG = tools.import_json(path)

    try:
        CFG["Biomes"]
    except:
        # no biomes? crash on purpose, you need that!
        print("Unable to get Biomes from CFG!")
        print(Exception)

    # this is the default CFG data
    Expecting = [
        ["Sector_Size", 4080],
        ["Noise_Size", 25],
        ["LineFidelity", 25],
        ["Terrain_Seed", random.randint(0, 100)],
    ]

    for Entry in Expecting:
        CFG[Entry[0]] = CFG.get(Entry[0], Entry[1])

    return CFG


def get():

    return CFG["Biomes"]["hl2_white_forest"]["terrain"]


def biome():

    return CFG["Biomes"]["hl2_white_forest"]
