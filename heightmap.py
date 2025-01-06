import numpy as np
from noise import pnoise2
import matplotlib.pyplot as plt
import random, itertools, math
import lines, sectors, tools


def build_heightmap_base(blocklist, Sector_Size, Noise_Size):

    global ContourMaps

    Extents = [0, 0, 0, 0]
    # x min, x max, y min, y max

    for block in blocklist:
        Extents[0] = min(Extents[0], block[0])
        Extents[1] = max(Extents[1], block[0])
        Extents[2] = min(Extents[2], block[1])
        Extents[3] = max(Extents[3], block[1])

    ContourMaps = {
        "x_scale": Sector_Size * (Extents[1] - Extents[0] + 1),
        "x_shift": Sector_Size * Extents[0],
        "y_scale": Sector_Size * (Extents[3] - Extents[2] + 1),
        "y_shift": Sector_Size * Extents[2],
        "width": Noise_Size * (Extents[1] - Extents[0] + 1),
        "height": Noise_Size * (Extents[3] - Extents[2] + 1),
    }

    return Extents


def bilinear_interpolation(Z, x, y):

    if len(Z) <= 1:
        return 0

    x = max(min(0.999, x), 0) * (len(Z) - 1)
    y = max(min(0.999, y), 0) * (len(Z[0]) - 1)

    # 1, 1 on a 3x3 grid
    # 1 * 3-1 = 1
    # let's get the outcome straight
    # 1,1 should refer to the 2nd-to-last vertex (so the last vertex can interpolate)
    # 0,0 should refer to the first vertex (0)

    # convert x,y 0-1 to grid co-ords relative to the size of Z + bounding
    x0 = int(x)
    y0 = int(y)

    # let's think for a second
    # gridsize = 30
    # 30 * 1 (farthest extent)
    # 30 + 1
    # remove 1, which means it breaks in the case of 1, but that's not even a case where you can interpolate
    # might add an edgecase check for it, why not

    # apparently it needs 2? one for the overflow, one for the +1? idk

    x1, y1 = x0 + 1, y0 + 1

    # Corner values
    Q00 = Z[x0][y0]
    Q01 = Z[x0][y1]
    Q10 = Z[x1][y0]
    Q11 = Z[x1][y1]

    # Interpolation weights
    # situation with the very end; x0 is x-1, so alphax = 1 = most interp possible
    alpha_x = (x) - x0
    alpha_y = (y) - y0

    # Interpolate along x for y0 and y1
    R0 = Q00 + alpha_x * (Q10 - Q00)
    R1 = Q01 + alpha_x * (Q11 - Q01)

    # Interpolate along y
    P = R0 + alpha_y * (R1 - R0)

    return P


def generate_perlin_noise(scale, octaves, persistence, lacunarity, seed):

    height = ContourMaps["height"]
    width = ContourMaps["width"]

    noise_array = np.zeros((height, width))
    for y in range(height):
        for x in range(width):
            noise_array[y][x] = pnoise2(
                x / scale,
                y / scale,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
                repeatx=width,
                repeaty=height,
                base=seed,
            )
    return noise_array


def display_perlin_layers(layers, cmap="viridis"):
    """Display multiple layers of Perlin noise."""
    num_layers = len(layers)
    fig, axs = plt.subplots(1, num_layers, figsize=(15, 5))
    for i, layer in enumerate(layers):
        axs[i].imshow(layer, cmap=cmap)
        axs[i].set_title(f"Layer {i + 1}")
        axs[i].axis("off")
    plt.tight_layout()
    plt.show()


def rescale_heightmap(arr, new_min, new_max):

    current_min = np.min(arr)
    current_max = np.max(arr)

    # Rescale to percentile range [0, 1]
    arr_normalized = (arr - current_min) / (current_max - current_min)

    current_min = np.min(arr_normalized)
    current_max = np.max(arr_normalized)

    # Scale to the new range [new_min, new_max]
    arr_rescaled = arr_normalized * (new_max - new_min) + new_min

    return arr_rescaled


def bleed(data, dir, strength=0.2, iterations=30, size=1):

    data = np.array(data, dtype=float)  # Convert to float for incremental changes
    rows, cols = data.shape
    for _ in range(iterations):
        # Copy the current state to a new array for updates
        new_data = data.copy()
        for i in range(0, rows):
            for j in range(0, cols):
                # Neighbor values
                neighbors = data[
                    max(i - size, 0) : min(i + 1 + size, rows),
                    max(j - size, 0) : min(j + 1 + size, cols),
                ]
                # Propagate higher values only
                # high_values = neighbors[neighbors > data[i, j]]
                nearby = list(itertools.chain(*neighbors))
                if len(nearby):
                    highest_value = min(nearby) if dir == "min" else max(nearby)

                    increment = strength * (highest_value - data[i, j])
                    new_data[i, j] += increment
        data = new_data  # Update the data for the next iteration
    return data


def generate_blank_map():

    return [
        [0 for _ in range(ContourMaps["height"])] for _ in range(ContourMaps["width"])
    ]


def realize_position(virtual_x, virtual_y):

    return ((virtual_x + 0.5) / ContourMaps["width"]) * ContourMaps[
        "x_scale"
    ] + ContourMaps["x_shift"], (
        (virtual_y + 0.5) / ContourMaps["height"]
    ) * ContourMaps[
        "y_scale"
    ] + ContourMaps[
        "y_shift"
    ]


def generate_heightmap_min_max(Sector_Size, Terrain):

    MinMap = generate_blank_map()
    MaxMap = generate_blank_map()

    for virtual_x in range(ContourMaps["width"]):
        for virtual_y in range(ContourMaps["height"]):

            real_x, real_y = realize_position(virtual_x, virtual_y)

            distance, height = lines.distance_to_line(real_x, real_y, 3)

            Sector = sectors.get_sector(
                math.floor(real_x / Sector_Size),
                math.floor(real_y / Sector_Size),
            )

            metric = min(
                max(
                    distance - Terrain["track_bias_base"],
                    0,
                )
                / Terrain["track_bias_slope"],
                1,
            )

            top = tools.linterp(
                Terrain["track_max"] + height,
                (Sector[0][1] * 16) - Terrain["minimum_tree_height"],
                metric,
            )
            bottom = tools.linterp(
                Terrain["track_min"] + height,
                (Sector[0][0] * 16),
                metric,
            )

            MinMap[virtual_x][virtual_y] = bottom
            MaxMap[virtual_x][virtual_y] = top

    ContourMaps["min_height"] = bleed(MinMap, "max")
    ContourMaps["max_height"] = bleed(MaxMap, "min")


def rescale_terrain(heightmap, virtual_x, virtual_y, Terrain):

    return tools.linterp(
        ContourMaps["max_height"][virtual_x][virtual_y],
        ContourMaps["min_height"][virtual_x][virtual_y],
        (Terrain["noise_multiplier"] * heightmap[virtual_x][virtual_y])
        + max(((1 - Terrain["noise_multiplier"]) * 0.5), 0),
    )


def carve_height(initial_height, intended_height, distance, Terrain):

    # this value is "how far away from intended are you allowed to go"
    deviation = (
        math.pow(
            max(
                0,
                (distance - Terrain["cut_basewidth"]) / Terrain["cut_scale"],
            ),
            Terrain["cut_power"],
        )
        * Terrain["cut_scale"]
    ) * Terrain["cut_slump"]

    return max(
        min(initial_height, intended_height + deviation), intended_height - deviation
    )


def cut_and_fill_heightmap(heightmap, Terrain):

    for virtual_x in range(len(heightmap)):
        for virtual_y in range(len(heightmap[0])):

            # converts the normalized position into one rescaled by the height min/max
            scaled = rescale_terrain(heightmap, virtual_x, virtual_y, Terrain)

            real_x, real_y = realize_position(virtual_x, virtual_y)

            distance, height = lines.distance_to_line(real_x, real_y, 3)

            result = carve_height(
                scaled, height + Terrain["cut_base_height"], distance, Terrain
            )

            heightmap[virtual_x][virtual_y] = result

    return heightmap


def generate_test_biomes(dimensions):

    Biome = generate_blank_map()

    for x in range(len(Biome)):
        for y in range(len(Biome[0])):
            Biome[x][y] = [x, y]

    Biome = rescale_heightmap(Biome, 0, 1)

    ContourMaps["biome"] = Biome


def query_height(real_x, real_y):

    virtual_x = (real_x - ContourMaps["x_shift"]) / (ContourMaps["x_scale"])
    virtual_y = (real_y - ContourMaps["y_shift"]) / (ContourMaps["y_scale"])

    height = bilinear_interpolation(ContourMaps["alpine_snow"], virtual_x, virtual_y)

    return height


def generate_biome_heightmaps(Biomes, Noise_Size, Terrain_Seed):

    for Biome in Biomes.items():

        base_biome_noisemap = generate_perlin_noise(
            Noise_Size / Biome[1]["terrain"]["noise_hill_resolution"],
            Biome[1]["terrain"]["noise_octaves"],
            Biome[1]["terrain"]["noise_persistence"],
            Biome[1]["terrain"]["noise_lacunarity"],
            Terrain_Seed,
        )

        normalized_heightmap = rescale_heightmap(base_biome_noisemap, 0, 1)

        ContourMaps[Biome[0]] = cut_and_fill_heightmap(
            normalized_heightmap, Biome[1]["terrain"]
        )
