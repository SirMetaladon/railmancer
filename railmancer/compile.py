from scipy.spatial import KDTree
import math, numpy as np, random
from railmancer import sectors, terrain, tools, heightmap, cfg, vmfpy


def point_generator(
    density_field,
    sector_data,
    num_dots,
    minimum_spacing,
    resolution=25,  # processing time goes up exponentially with this fyi
):

    sector_size = cfg.get("sector_real_size")
    """
    Generate dots distributed according to a density field, with improved apportioning.

    Parameters:
        density_field: function that takes (x, y) and returns the density value.
        bounds: tuple of ((x_min, x_max), (y_min, y_max)) for the plane bounds.
        num_dots: int, the number of dots to generate.
        resolution: int, the grid resolution for sampling probabilities.

    Returns:
        np.ndarray of shape (N, 2) with dot coordinates.
    """
    x_min, x_max = sector_data["x"] * sector_size, (sector_data["x"] + 1) * sector_size
    y_min, y_max = sector_data["y"] * sector_size, (sector_data["y"] + 1) * sector_size

    # Create a grid over the plane
    x_vals = np.linspace(x_min, x_max, resolution)
    y_vals = np.linspace(y_min, y_max, resolution)
    xx, yy = np.meshgrid(x_vals, y_vals)

    # Compute density values on the grid
    density_grid = np.vectorize(density_field)(xx, yy, sector_data)
    density_grid = np.maximum(density_grid, 0)  # Ensure no negative densities

    # Normalize density values to create a probability distribution
    density_sum = np.sum(density_grid)
    if density_sum == 0:
        raise ValueError("Density field integrates to zero; no dots can be placed.")
    density_prob = density_grid / density_sum

    # Flatten grid for sampling
    flat_prob = density_prob.flatten()
    flat_x = xx.flatten()
    flat_y = yy.flatten()

    # Sample indices from the flattened grid based on the density probabilities
    sampled_indices = np.random.choice(len(flat_prob), size=num_dots, p=flat_prob)
    sampled_points = np.column_stack((flat_x[sampled_indices], flat_y[sampled_indices]))

    # Enforce minimum distance constraint using KD-tree
    dots = []
    kdtree = False

    for x, y in sampled_points:
        dots.append((x, y))  # there's definitely a better way to do this
    '''
    for x, y in sampled_points:
        """density = density_field(x, y, sector_data)
        if density <= 0:
            continue"""  # should not be needed - the density field is programmed to never go below 0

        if x == 0 and y == 0:
            print("Got one!", sector_data)
            continue

        if kdtree:
            distances, _ = kdtree.query([x, y], k=1)
            if distances < minimum_spacing:
                continue

        # Accept the point
        dots.append((x, y))
        kdtree = KDTree(dots)'''

    return np.array(dots)


# Example usage
def density_field(x, y, sector_data):

    BaseX = math.floor(x / 4080)
    BaseY = math.floor(y / 4080)

    if not sector_data:
        return 0

    else:

        neighbors = sector_data["neighbors"]

        Value = 1
        Coefficient = 4

        # True = there is a wall in the +x direction, so if the co-ords are 0,0, the wall should start at 3060 and go up to Coefficient x the normal height by the time we have reached 4080
        if neighbors[1] is False:
            Value += max(Coefficient * ((x - (BaseX * 4080) - 3060) / 1020), 0)
        # -y direction
        if neighbors[2] is False:
            Value += max(Coefficient * ((-y + (BaseY * 4080) + 1020) / 1020), 0)
        # -x direction
        if neighbors[3] is False:
            Value += max(Coefficient * ((-x + (BaseX * 4080) + 1020) / 1020), 0)
        # +y direction
        if neighbors[0] is False:
            Value += max(Coefficient * ((y - (BaseY * 4080) - 3060) / 1020), 0)

    return max(Value, 0)


def scatter_placables():

    Terrain = terrain.get()

    for sector_data in sectors.get_all().values():

        distribute(
            Terrain.get("model_minimum_distance", 110),
            Terrain.get("maximum_models_per_sector", 125),
            sector_data,
        )


def distribute(min_distance, TotalPoints, sector_data):

    Points = point_generator(
        density_field, sector_data, int(TotalPoints * 2), min_distance
    )

    Terrain = terrain.get()

    for Point in Points:

        if TotalPoints:
            TotalPoints -= 1

            ModelData = terrain.biome()["models"]
            Choices = list(ModelData.keys())
            Weights = tools.extract(ModelData, Choices, "weight", 0)

            ModelPath = random.choices(Choices, Weights)[0]
            Model = ModelData[ModelPath]

            realdist, _ = sectors.distance_to_line([Point[0], Point[1], 0], sector_data)
            dist = realdist - Model["exclusion_radius"]

            Hardline = Terrain.get("tree_hard_distance", 128)
            Softline = Terrain.get("tree_fade_distance", 300)

            if dist <= Hardline:
                continue
            elif dist > Hardline and dist <= Softline:

                Over = (dist - Hardline) / (Softline - Hardline)
                if random.random() > Over:
                    continue

            StumpSize = Model["base_radius"]

            HeightSamples = heightmap.height_sample(
                Point[0], Point[1], 5, StumpSize, sector_data
            )

            ModelSteepnessAllowed = Model.get("steepness", 999)
            LowestSteepnessAllowed = Model.get("min_steep", -999)

            CurrentSteepness = (max(HeightSamples) - min(HeightSamples)) / (
                StumpSize * 2
            )

            if CurrentSteepness > ModelSteepnessAllowed:
                continue
            if CurrentSteepness < LowestSteepnessAllowed:
                continue

            vmfpy.add_entity(
                {
                    "pos-x": Point[0],
                    "pos-y": Point[1],
                    "pos-z": min(HeightSamples) + Model.get("height_offset", 0),
                    "mdl": ModelPath,
                    "ang-yaw": random.randrange(-180, 180),
                    "ang-pitch": random.randrange(-4, 4),
                    "ang-roll": random.randrange(-4, 4),
                    "shadows": "noself",
                    "visgroup": "22",
                }
            )


def compile_displacement(raw_displacement, sector_data):

    X_Start, X_End, Y_Start, Y_End, Z_Start, Z_End = raw_displacement[:6]

    # 8 multiplier due to the range function below (the power of the displacement is 3, or 2^3 = 8)
    scale_x = (X_Start - X_End) / -8
    scale_y = (Y_Start - Y_End) / 8
    shift_x = X_Start
    shift_y = Y_End

    posgrid = [
        [(x * scale_x + shift_x, y * scale_y + shift_y, 0) for y in range(9)]
        for x in range(9)
    ]

    heights = [
        [
            heightmap.query_field("height", position, sector_data) - Z_End
            for position in x_layer
        ]
        for x_layer in posgrid
    ]
    # reconfigure this later to check the specific sub-biome data for this exact position
    alphas = [
        [
            heightmap.query_alpha(position, terrain.get(), sector_data)
            for position in x_layer
        ]
        for x_layer in posgrid
    ]

    return heights, alphas


def sector_coords_to_subdivided_displacements(
    block_x: int, block_y: int, block_z: int, subdivision, texture
):

    Disps = [
        [
            (block_x + x / subdivision) * 16 * 255,
            (block_x + ((x + 1) / subdivision)) * 16 * 255,
            (block_y + y / subdivision) * 16 * 255,
            (block_y + ((y + 1) / subdivision)) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
            texture,
        ]
        for y in range(subdivision)
        for x in range(subdivision)
    ]

    return Disps


def compile_sectors_to_brushes():

    subdivisions = cfg.get("sector_displacement_subdivision_rate")

    for sector_data in sectors.get_all().values():

        x, y, z = sector_data["x"], sector_data["y"], sector_data["floor"]

        create_scenery_block(sector_data)
        raw_displacements = sector_coords_to_subdivided_displacements(
            x,
            y,
            z,
            subdivisions,
            terrain.get().get("texture_ground", "dev/dev_blendmeasure"),
        )

        for raw_disp in raw_displacements:

            heights, alphas = compile_displacement(raw_disp, sector_data)

            finished_displacement = raw_disp + [
                vmfpy.data_to_dispinfo(raw_disp, heights, alphas)
            ]

            vmfpy.add_brush(finished_displacement)


def create_scenery_block(sector_data):
    block_x, block_y, block_floor, block_ceiling = (
        sector_data["x"],
        sector_data["y"],
        sector_data["floor"],
        sector_data["ceiling"],
    )

    vmfpy.floor(block_x, block_y, block_floor),
    vmfpy.ceiling(block_x, block_y, block_ceiling),

    for dir in range(4):

        adjacent_sector_id = sector_data["neighbors"][dir]

        adjacent_sector = sectors.get(adjacent_sector_id, False)

        if adjacent_sector is False:

            vmfpy.wall(block_x, block_y, block_floor, block_ceiling, dir, "ceiling")

        else:
            nearby_floor, nearby_ceiling = (
                adjacent_sector["floor"],
                adjacent_sector["ceiling"],
            )

            if nearby_floor > block_floor:

                vmfpy.wall(block_x, block_y, nearby_floor, block_floor, dir)

            if nearby_ceiling < block_ceiling:

                vmfpy.wall(
                    block_x, block_y, nearby_ceiling, block_ceiling, dir, "ceiling"
                )
