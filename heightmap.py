import numpy as np
from noise import pnoise3
import matplotlib.pyplot as plt
import random, itertools, math
import lines, sectors, tools, terrain


def build_heightmap_base(Sector_Size, Noise_Size, SectorsPerGrid):

    global biome_maps

    """Extents = [0, 0, 0, 0]
    # x min, x max, y min, y max

    for block in blocklist:
        Extents[0] = min(Extents[0], block[0])
        Extents[1] = max(Extents[1], block[0])
        Extents[2] = min(Extents[2], block[1])
        Extents[3] = max(Extents[3], block[1])"""

    biome_maps = {
        "sector_span_physical": Sector_Size,
        "sector_span_noise": Noise_Size,
        # "sector_shift": Sector_Size * ((SectorsPerGrid / 2) - 1),
        "overall_span_noise": Noise_Size * SectorsPerGrid,
    }


def bilinear_interpolation(Z, x, y):

    if len(Z) <= 1:
        return 0

    x_actual_pos = max(min(0.999, x), 0) * (len(Z) - 1)
    y_actual_pos = max(min(0.999, y), 0) * (len(Z[0]) - 1)

    LeftXCoord = int(x)
    BottomYCoord = int(y)

    RightXCoord, TopYCoord = LeftXCoord + 1, BottomYCoord + 1

    BottomLeftCornerAlpha = Z[LeftXCoord][BottomYCoord]
    TopLeftCornerAlpha = Z[LeftXCoord][TopYCoord]
    BottomRightCornerAlpha = Z[RightXCoord][BottomYCoord]
    TopRightCornerAlpha = Z[RightXCoord][TopYCoord]

    interp_ratio_x = x_actual_pos - LeftXCoord
    interp_ratio_y = y_actual_pos - BottomYCoord

    interpolated_x_start = BottomLeftCornerAlpha + interp_ratio_x * (
        BottomRightCornerAlpha - BottomLeftCornerAlpha
    )
    interpolated_x_end = TopLeftCornerAlpha + interp_ratio_x * (
        TopRightCornerAlpha - TopLeftCornerAlpha
    )

    output = interpolated_x_start + interp_ratio_y * (
        interpolated_x_end - interpolated_x_start
    )

    return output


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


def generate_blank_map(dimensions, length):

    size = range(length)

    if dimensions == 2:

        return [[0 for _ in size] for _ in size]

    if dimensions == 3:

        # 3-dimensional array of zeroes
        return [[[0 for _ in size] for _ in size] for _ in size]


def convert_virtual_to_real_pos(virtual_x, virtual_y, Sector):

    # virtual X and Y are 0-1 within the sector
    sector_x, sector_y = Sector["x"], Sector["y"]

    real_x = (sector_x + virtual_x) * biome_maps["sector_span_physical"]
    real_y = (sector_y + virtual_y) * biome_maps["sector_span_physical"]

    return real_x, real_y


def convert_real_to_noise_pos(real_x, real_y, sector_data):

    sector_x, sector_y = sector_data["x"], sector_data["y"]

    noise_x = (real_x / biome_maps["sector_span_physical"] - sector_x) * biome_maps[
        "sector_span_noise"
    ]
    noise_y = (real_y / biome_maps["sector_span_physical"] - sector_y) * biome_maps[
        "sector_span_noise"
    ]

    return noise_x, noise_y


def generate_sector_heightmaps(Sectors):
    #

    for Sector in Sectors.items():

        MinMap = generate_blank_map(2, biome_maps["sector_span_noise"])
        MaxMap = generate_blank_map(2, biome_maps["sector_span_noise"])

        for noise_x in range(biome_maps["sector_span_noise"]):
            for noise_y in range(biome_maps["sector_span_noise"]):

                virtual_x, virtual_y = (
                    noise_x / biome_maps["sector_span_noise"],
                    noise_y / biome_maps["sector_span_noise"],
                )

                real_x, real_y = convert_virtual_to_real_pos(
                    virtual_x, virtual_y, Sector[1][0]
                )

                # replace with "get terrain at this point" feature
                Terrain = terrain.get()

                distance, height = lines.distance_to_line(real_x, real_y)

                TopOfBlock = Sector[1][0]["ceiling"]
                BottomOfBlock = Sector[1][0]["floor"]

                Top_of_Terrain = (TopOfBlock * 16) - Terrain["minimum_tree_height"]

                metric = min(
                    max(
                        distance - Terrain["track_bias_base"],
                        0,
                    )
                    * (Terrain["track_bias_slope"] / Top_of_Terrain),
                    1,
                )

                top = tools.linterp(
                    Terrain["track_max"] + height,
                    Top_of_Terrain,
                    metric,
                )
                bottom = tools.linterp(
                    Terrain["track_min"] + height,
                    (BottomOfBlock * 16),
                    metric,
                )

                MinMap[noise_x][noise_y] = bottom
                MaxMap[noise_x][noise_y] = top

        Sector[1][0]["minmap"] = bleed(MaxMap, "min")
        Sector[1][0]["maxmap"] = bleed(MinMap, "max")


def rescale_terrain(sector, virtual_x, virtual_y, Terrain):

    return tools.linterp(
        sector[6][virtual_x][virtual_y],
        sector[5][virtual_x][virtual_y],
        (Terrain["noise_multiplier"] * biome_maps["hl2_white_forest"])
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


def generate_heightmap_node(sector, virtual_x, virtual_y):

    Terrain = terrain.get()

    # converts the normalized position into one rescaled by the height min/max
    scaled = rescale_terrain(virtual_x, virtual_y, Terrain)

    real_x, real_y = convert_virtual_to_real_pos(virtual_x, virtual_y)

    distance, height = lines.distance_to_line(real_x, real_y, 3)

    result = carve_height(
        scaled, height + Terrain["cut_base_height"], distance, Terrain
    )

    sector[0]["heightmap"][virtual_x][virtual_y] = result


def cut_and_fill_sector_heightmaps(Sectors):

    for sector in Sectors.items():

        # since it's guarenteed to be square, and all the same size
        heightmap = sector[1][0]["heightmap"]
        poll_values = np.linspace(0, 1, len(heightmap))

        # print(heightmap)

        for virtual_x in poll_values:
            for virtual_y in poll_values:

                generate_heightmap_node(sector[1], virtual_x, virtual_y)


def query_height(real_x, real_y, sector):

    virtual_x, virtual_y = convert_real_to_noise_pos(real_x, real_y, sector[0])

    height = bilinear_interpolation(sector[0]["heightmap"], virtual_x, virtual_y)

    return height


def sample_terrain(x, y, z=10):

    Terrain = terrain.get()

    scale = biome_maps["overall_span_noise"] / Terrain["noise_hill_resolution"]

    return pnoise3(
        x / scale,
        y / scale,
        z / scale,
        octaves=Terrain["noise_octaves"],
        persistence=Terrain["noise_persistence"],
        lacunarity=Terrain["noise_lacunarity"],
        base=Terrain["seed"],
    )
