import numpy as np
from noise import pnoise3
import matplotlib.pyplot as plt
import random, itertools, math, time
from railmancer import lines, sectors, tools, terrain, entities, cfg


def build_heightmap_base():

    global biome_maps

    """Extents = [0, 0, 0, 0]
    # x min, x max, y min, y max

    for block in blocklist:
        Extents[0] = min(Extents[0], block[0])
        Extents[1] = max(Extents[1], block[0])
        Extents[2] = min(Extents[2], block[1])
        Extents[3] = max(Extents[3], block[1])"""

    biome_maps = {
        "sector_span_physical": cfg.get("sector_size"),
        "sector_span_noise": cfg.get("Noise_Size"),
        # "sector_shift": sector_size * ((SectorsPerGrid / 2) - 1),
        "overall_span_noise": cfg.get("Noise_Size") * cfg.get("sectors_per_map"),
    }


def get_four_nearest_noise_values(
    grid, LeftXCoord, RightXCoord, TopYCoord, BottomYCoord
):

    Limit = len(grid)

    if LeftXCoord < 0 or LeftXCoord > Limit:
        return False
    if RightXCoord < 0 or RightXCoord > Limit:
        return False
    if TopYCoord < 0 or TopYCoord > Limit:
        return False
    if BottomYCoord < 0 or BottomYCoord > Limit:
        return False

    BottomLeftCornerAlpha = grid[LeftXCoord][BottomYCoord]
    TopLeftCornerAlpha = grid[LeftXCoord][TopYCoord]
    BottomRightCornerAlpha = grid[RightXCoord][BottomYCoord]
    TopRightCornerAlpha = grid[RightXCoord][TopYCoord]

    if BottomLeftCornerAlpha is False:
        return False
    if TopLeftCornerAlpha is False:
        return False
    if BottomRightCornerAlpha is False:
        return False
    if TopRightCornerAlpha is False:
        return False

    return (
        BottomLeftCornerAlpha,
        TopLeftCornerAlpha,
        BottomRightCornerAlpha,
        TopRightCornerAlpha,
    )


def sector_interpolator(sector_object, noise_x, noise_y, field):

    if sector_object is None:
        return False

    LeftXCoord = noise_x
    BottomYCoord = noise_y

    RightXCoord, TopYCoord = LeftXCoord + 1, BottomYCoord + 1

    Corners = get_four_nearest_noise_values(
        sector_object["grid"][field], LeftXCoord, RightXCoord, TopYCoord, BottomYCoord
    )

    if Corners == False:
        return False

    (
        BottomLeftCornerAlpha,
        TopLeftCornerAlpha,
        BottomRightCornerAlpha,
        TopRightCornerAlpha,
    ) = Corners

    interp_ratio_x = noise_x - LeftXCoord
    interp_ratio_y = noise_y - BottomYCoord

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


def blank_list_grid(dimensions, length, fill=0):

    size = range(length)

    if dimensions == 2:

        return [[fill for _ in size] for _ in size]

    if dimensions == 3:

        # 3-dimensional array of zeroes
        return [[[fill for _ in size] for _ in size] for _ in size]


def convert_noise_to_real_pos(noise_x, noise_y, sector_data):

    sector_x, sector_y = sector_data["x"], sector_data["y"]

    # sector x/y are integers relative to the overall grid (-3 to 4)
    # virtual x/y are floats fractions within the sector (0 to 1)
    # noise x/y are integers related to points within the sector (0 to span-1)

    virtual_x = noise_x / (biome_maps["sector_span_noise"] - 1)
    virtual_y = noise_y / (biome_maps["sector_span_noise"] - 1)

    real_x = (sector_x + virtual_x) * biome_maps["sector_span_physical"]
    real_y = (sector_y + virtual_y) * biome_maps["sector_span_physical"]

    return real_x, real_y


def convert_real_to_noise_pos(real_x, real_y, sector_data):

    sector_x, sector_y = sector_data["x"], sector_data["y"]

    # sector x/y are integers relative to the overall grid (-3 to 4)
    # virtual x/y are floats fractions within the sector (0 to 1)
    # noise x/y are integers related to points within the sector (0 to span-1)

    virtual_x = (real_x / biome_maps["sector_span_physical"]) - sector_x
    virtual_y = (real_y / biome_maps["sector_span_physical"]) - sector_y

    noise_x = virtual_x * (biome_maps["sector_span_noise"] - 1)
    noise_y = virtual_y * (biome_maps["sector_span_noise"] - 1)

    return noise_x, noise_y


def generate_sector_heightmaps():

    for sector_data in sectors.get_all().values():

        MinMap = blank_list_grid(2, biome_maps["sector_span_noise"])
        MaxMap = blank_list_grid(2, biome_maps["sector_span_noise"])
        sector_data["heightmap"] = blank_list_grid(2, biome_maps["sector_span_noise"])

        for noise_x in range(biome_maps["sector_span_noise"]):
            for noise_y in range(biome_maps["sector_span_noise"]):

                real_x, real_y = convert_noise_to_real_pos(
                    noise_x, noise_y, sector_data
                )

                # replace with "get terrain at this point" feature
                Terrain = terrain.get()

                distance, height = lines.distance_to_line(real_x, real_y)

                TopOfBlock = sector_data["ceiling"]
                BottomOfBlock = sector_data["floor"]

                Top_of_Terrain = (TopOfBlock * 16) - Terrain[
                    "height_terrain_minimum_to_ceiling"
                ]

                Dist_Terrain_Slope = (
                    distance - Terrain["height_terrain_flat_in_radius_around_track"]
                )

                Dist_Terrain_Slope_Start = max(
                    Dist_Terrain_Slope,
                    0,
                )

                metric = min(
                    Dist_Terrain_Slope_Start
                    / Terrain["height_terrain_transition_to_tracks_distance"],
                    1,
                )

                top = tools.linterp(
                    Terrain["track_max"] + height,
                    Top_of_Terrain,
                    metric,
                )
                bottom = tools.linterp(
                    Terrain["track_min"] + height,
                    (BottomOfBlock * 16) + Terrain["height_terrain_minimum_to_floor"],
                    metric,
                )

                MinMap[noise_x][noise_y] = int(bottom)
                MaxMap[noise_x][noise_y] = int(top)

        sector_data["maxmap"] = MaxMap
        sector_data["minmap"] = MinMap


def rescale_terrain(sector_data, noise_x, noise_y, real_x, real_y, Terrain):

    Min = sector_data["minmap"][noise_x][noise_y]
    Max = sector_data["maxmap"][noise_x][noise_y]

    NoiseSample = 0  # sample_realspace_noise(real_x, real_y, 10)
    NoiseValue = Terrain["noise_deviation_multiplier"] * NoiseSample

    return tools.linterp(Min, Max, 0.5 + NoiseValue)


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


def generate_heightmap_node(sector_object, noise_x, noise_y):

    sector_data = sector_object[0]

    Terrain = terrain.get()

    real_x, real_y = convert_noise_to_real_pos(noise_x, noise_y, sector_data)

    # converts the normalized position into one rescaled by the height min/max
    scaled = rescale_terrain(sector_data, noise_x, noise_y, real_x, real_y, Terrain)

    distance, height = lines.distance_to_line(real_x, real_y)

    if False:  # if True, this is "virgin" terrain before cut and fill
        result = carve_height(
            scaled, height + Terrain["height_track_to_terrain"], distance, Terrain
        )
    else:
        result = scaled + Terrain["height_track_to_terrain"]

    sector_data["heightmap"][noise_x][noise_y] = int(result)


def cut_and_fill_sector_heightmaps():

    for sector in sectors.get_all().items():

        sector_object = sector[1]

        # since it's guarenteed to be square, and all the same size
        heightmap = sector_object[0]["heightmap"]
        poll_values = range(len(heightmap))

        # 2 gives 0, 1
        # 0, 1 needs to become 0,1 in the linear transform thingy
        # therefore, the divisor needs to be 1

        for noise_x in poll_values:
            for noise_y in poll_values:

                generate_heightmap_node(sector_object, noise_x, noise_y)


def query_field(real_x, real_y, sector_object):

    # 2048,2048 (middle of the square, should return noise x/y = 1,1

    noise_x, noise_y = convert_real_to_noise_pos(real_x, real_y, sector_object[0])

    height = sector_interpolator(sector_object, noise_x, noise_y)

    return height


def curb_noise(v):
    """if v < -curb_start:
        residual = (v + curb_start) * (curb_width)
        return -curb_start + residual

    elif v > curb_start:
        residual = (v - curb_start) * (curb_width)
        return curb_start + residual
    else:
        return v"""
    if v > 0.5 or v < -0.5:
        return -v
    else:
        return v


def sample_realspace_noise(x, y, z):

    Terrain = terrain.get()

    scale = biome_maps["overall_span_noise"] * Terrain["noise_hill_resolution"]

    noise = pnoise3(
        x / scale,
        y / scale,
        z / scale,
        octaves=Terrain["noise_octaves"],
        persistence=Terrain["noise_persistence"],
        lacunarity=Terrain["noise_lacunarity"],
        base=Terrain["seed"],
    )

    return noise  # curb_noise(noise)


def height_sample(real_x, real_y, samples, radius, sector):

    # start with one in the center for good measure
    Heights = [query_field(sector, "height", real_x, real_y)]

    SectorSize = 360 / samples
    Arm = [radius, 0]

    for Slice in range(samples):

        offset = tools.rot_z(Arm, Slice * SectorSize)

        Example = query_field(sector, "height", real_x + offset[0], real_y + offset[1])
        Heights += [Example]

    return Heights


def smooth_min_max_maps():

    # pseudocode:
    #

    # for every sector, run through all the main entries and smooth them to neighbors

    for sector in sectors.get_all().values():

        print(query_field(sector, "height", 0, 0))

    """for sector in sectors.get_all().items():

        sector_object = sector[1]

        # since it's guarenteed to be square, and all the same size
        heightmap = sector_object[0]["heightmap"]
        poll_values = range(len(heightmap))

        # 2 gives 0, 1
        # 0, 1 needs to become 0,1 in the linear transform thingy
        # therefore, the divisor needs to be 1

        for noise_x in poll_values:
            for noise_y in poll_values:

                generate_heightmap_node(sector_object, noise_x, noise_y)"""
