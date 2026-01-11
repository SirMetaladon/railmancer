from railmancer import cfg

# this will be retrofitted later into a tool for converting points in 2d/3d space into biome blend data


def get():

    return cfg.get("Biomes")["hl2_white_forest"]["terrain"]


def biome():

    return cfg.get("Biomes")["hl2_white_forest"]
