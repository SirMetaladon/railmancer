from railmancer import cfg

# this will be retrofitted later into a tool for converting points in 2d/3d space into biome blend data.
# Scatter density is a function of (x, y, z) so a field from here can plug in.
# That field is not implemented; compile uses a flat base of 1 until it is.


def get():

    return cfg.get("Biomes")["hl2_white_forest"]["terrain"]


def biome():

    return cfg.get("Biomes")["hl2_white_forest"]
