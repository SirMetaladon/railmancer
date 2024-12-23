import random, math
import noisetest, curvature, scatter, pathfinder, tools, vmfpy
import numpy as np


def bounds(blocklist):

    Extents = [0, 0, 0, 0]
    # x min, x max, y min, y max

    for block in blocklist:
        Extents[0] = min(Extents[0], block[0])
        Extents[1] = max(Extents[1], block[0])
        Extents[2] = min(Extents[2], block[1])
        Extents[3] = max(Extents[3], block[1])

    return Extents


def query_height(real_x, real_y):

    virtual_x = (real_x - ContourMap["x_shift"]) / (ContourMap["x_scale"])
    virtual_y = (real_y - ContourMap["y_shift"]) / (ContourMap["y_scale"])

    height = noisetest.bilinear_interpolation(ContourMap["map"], virtual_x, virtual_y)

    return height


def height_sample(real_x, real_y, samples, radius):

    global Entities

    SectorSize = 360 / samples
    Heights = [query_height(real_x, real_y)]
    Arm = [radius, 0]

    for Slice in range(samples):

        offset = tools.rot_z(Arm, Slice * SectorSize)

        Example = query_height(real_x + offset[0], real_y + offset[1])
        Heights += [Example]

        # Entities += [vmfpy.frog(real_x + offset[0], real_y + offset[1], Example)]

    return Heights


def twodify(LineObject):

    List = []
    for Subvector in LineObject:

        List += [np.array([Subvector[0], Subvector[1]])]

    return List


def distance_to_line(real_x, real_y):
    # rough pseudocode:
    # determine what segment we're on (query endpoints + 2/3rds and 1/3rd point for each + compare distances)
    # for that segment, use newton-style narrowing until the distance change is less than 5 per jump or something

    # BETTER PLAN:
    # there's got to be some way where I can run a few layers on ALL lines (newtonian progression), then run a simple calculation to
    # guess an asemptote on which one might eventually arrive. If one is far but racing in, it's much more likely than one that is
    # close but barely making progress even while covering substantial portions of the line.
    # What if we evaluated all lines, then too the top 20% of ones who made the most progress towards it, as a function of percentage away from it?

    target_point = np.array([real_x, real_y])
    Shortest = 999999

    # dumb "check everything" solution
    for Subsegment in Beziers:
        ts = np.linspace(0, 1, 20)
        # make this scale with the approximate size of the line segment?

        for t in ts:
            bezier_pt = np.array([curvature.bezier(t, twodify(Subsegment))])
            distance = np.linalg.norm(bezier_pt - target_point)
            Shortest = min(distance, Shortest)

    """
    # Find the t with the minimum distance
    min_index = np.argmin(distances)
    closest_t = ts[min_index]"""

    return Shortest  # distances[closest_t]


def distribute(bounds, models, min_distance, num_dots):

    def flat_field(x, y):
        return 0.5

    EntsOut = []
    Points = scatter.point_generator(flat_field, bounds, num_dots, min_distance)
    # scatter.density_field #need to convert this function into the modular field I thought of
    for Point in Points:

        Model = random.choice(models)

        if distance_to_line(Point[0], Point[1]) <= ExclusionRadius[Model]:
            # this needs a per-model lookup table
            # current number is roughly 128 (track width from center) + tree exclusion radius
            continue

        StumpRadius = 55

        HeightSamples = height_sample(Point[0], Point[1], 5, StumpRadius)

        if (
            (max(HeightSamples) - min(HeightSamples)) / (StumpRadius * 2)
        ) > Terrain_cfg["too_steep"]:
            continue

        EntsOut += [
            {
                "pos-x": Point[0],
                "pos-y": Point[1],
                "pos-z": min(HeightSamples),
                "mdl": Model,
                "ang-yaw": random.randrange(-180, 180),
            }
        ]
    return EntsOut


def row_encode(heights: list):

    rot = [list(row) for row in zip(*heights)][::-1]

    String = ""
    for x in range(9):
        Row = ""
        for entry in rot[x]:
            Row += str(round(entry, 3)) + " "

        Row.strip()

        String += '\n    				"row' + str(x) + '" "' + Row + '"'

    return String


def query_alpha(real_x, real_y):

    dist = distance_to_line(real_x, real_y)

    HeightSamples = height_sample(real_x, real_y, 6, 20)

    OverSteep = 1 - (((max(HeightSamples) - min(HeightSamples)) / (40)) - 1 / 2)

    1 - (3 / 3 - 2 / 3)

    return min(min(max(0, (dist) / 3), 255), min(255 * OverSteep, 255))


def displacement_build(X_Start, X_End, Y_Start, Y_End, Z_Start, Z_End):

    scale_x = (X_Start - X_End) / -8
    scale_y = (Y_Start - Y_End) / 8  # multiplier due to the range function below
    shift_x = X_Start
    shift_y = Y_End

    posgrid = [
        [(x * scale_x + shift_x, y * scale_y + shift_y) for y in range(9)]
        for x in range(9)
    ]

    heights = [
        [query_height(position[0], position[1]) for position in x_layer]
        for x_layer in posgrid
    ]

    alphas = [
        [query_alpha(position[0], position[1]) for position in x_layer]
        for x_layer in posgrid
    ]

    """
    for x_layer in posgrid:  # debugging frogs for displacement vertexes
        for pos in x_layer:
            Entities += [frog(pos[0], pos[1], 350)]
    #"""
    # for some reason this is needed... sometimes

    return f"""			dispinfo
			{{
				"power" "3"
				"startposition" "[{min(X_Start,X_End)} {min(Y_Start,Y_End)} {0}]"
				"flags" "0"
				"elevation" "0"
				"subdiv" "0"
				normals
				{{
					"row0" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row1" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row2" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row3" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row4" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row5" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row6" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row7" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row8" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
				}}
				distances
				{{{row_encode(heights)}
				}}
				offsets
				{{
					"row0" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row1" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row2" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row3" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row4" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row5" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row6" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row7" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row8" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
				}}
				offset_normals
				{{
					"row0" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row1" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row2" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row3" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row4" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row5" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row6" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row7" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
					"row8" "0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1 0 0 1"
				}}
				alphas
				{{{row_encode(alphas)}
				}}
				triangle_tags
				{{
					"row0" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row1" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row2" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row3" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row4" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row5" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row6" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
					"row7" "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
				}}
				allowed_verts
				{{
					"10" "-1 -1 -1 -1 -1 -1 -1 -1 -1 -1"
				}}
			}}"""


def linterp(a, b, x):

    return a * (1 - x) + b * x


def rescale_terrain(initial_height, distance):

    metric = (
        min(
            max(distance - Terrain_cfg["track_bias_base"], 0),
            Terrain_cfg["track_bias_slope"],
        )
        / Terrain_cfg["track_bias_slope"]
    )  # 2 modules away, plus a track width buffer

    # initial_height is going to be somewhere in the range of 0 to 1400, roughly
    # we need to make it go from 0 to 400 at 0 distance, and 400 to 1400 at 2 blocks away (8160 distance)

    top = linterp(Terrain_cfg["track_max"], Terrain_cfg["bias_max"], metric)
    bottom = linterp(Terrain_cfg["track_min"], Terrain_cfg["bias_min"], metric)

    depth = top - bottom

    normalized = initial_height / (
        Terrain_cfg["overall_max"] - Terrain_cfg["overall_min"]
    )

    return (normalized * depth) + bottom


def carve_height(initial_height, intended_height, distance):

    # this value is "how far away from intended are you allowed to go"
    deviation = (
        math.pow(
            max(
                0, (distance - Terrain_cfg["cut_basewidth"]) / Terrain_cfg["cut_scale"]
            ),
            Terrain_cfg["cut_power"],
        )
        * Terrain_cfg["cut_scale"]
    ) * Terrain_cfg["cut_slump"]

    return max(
        min(initial_height, intended_height + deviation), intended_height - deviation
    )


def cut_and_fill_heightmap(heightmap, scale_x, shove_x, scale_y, shove_y):

    for virtual_x in range(len(heightmap)):
        for virtual_y in range(len(heightmap[0])):

            real_x = ((virtual_x + 0.5) / len(heightmap)) * scale_x + shove_x
            real_y = ((virtual_y + 0.5) / len(heightmap[0])) * scale_y + shove_y

            # to test the gridscale of the heightmap
            # Entities += [frog(real_x, real_y, 250)]

            distance = distance_to_line(real_x, real_y)

            scaled = rescale_terrain(heightmap[virtual_x][virtual_y], distance)

            result = carve_height(scaled, 164, distance)

            heightmap[virtual_x][virtual_y] = result

    return heightmap


def main():

    tools.click("total")
    tools.click("submodule")

    global Entities, ContourMap, Line, Beziers, Brushes, ExclusionRadius, Terrain_cfg

    Terrain_cfg = {
        "overall_max": 1400,
        "overall_min": -16,
        "track_bias_slope": 1500,
        "track_bias_base": 500,
        "cut_power": 1.5,  # curve shape - goes from 1 (flat slope) to inf (really steep and agressive)
        "cut_scale": 150,  # this controls the height of a 1-doubling for that power; think scale 10 on power 2 = the curve intersects at dist = 20, clamp = 40
        "cut_basewidth": 240,  # how far out the curve starts - think flat area under the track before the cut/fill starts
        "cut_slump": 0.7,  # this value scales it down a bit so it's not so steep on a 45 degree angle
        "bias_max": 1400,
        "bias_min": 0,
        "track_max": 600,
        "track_min": 0,
        "too_steep": 4 / 5,
    }

    FancyDisplay = False

    ExclusionRadius = {
        "models/props_foliage/tree_pine_extrasmall_snow.mdl": 300,
        "models/props_foliage/tree_pine_small_snow.mdl": 280,
        "models/props_foliage/tree_pine_huge_snow.mdl": 350,
    }

    Blocks = [
        [0, 0, 0],
        [1, 0, 0],
        [-1, 0, 0],
        [0, 1, 0],
        [1, 1, 0],
        [-1, 1, 0],
        # [0, 2, 0],
        # [1, 2, 0],
        # [-1, 2, 0],
        # [0, 3, 0],
        # [1, 3, 0],
        # [-1, 3, 0],
    ]

    Extents = bounds(Blocks)

    Brushes = []

    Line, Entities = pathfinder.solve(
        [2040, -32, 208], -90, [2040 + 4080, (4080 * 2) - 32, 208], -90
    )

    Beziers = curvature.generate_line(Line)

    elapsed = tools.display_time(tools.click("submodule"))
    print("Line generation complete in " + elapsed)

    if FancyDisplay:
        curvature.display_path(Beziers, Line)

    """rough pseudocode for converting between blocklists and module outputs

    for every incoming block-grid coordinates:

    place a floor and ceiling at the correct height
    populate a dict with the coordinates in x+" "y format with the Z value of that block

    scan the contents of the dict and request all 4 pairs of that block + the surrounding blocks

    if that pair exists (meaning that both coordinates show up in the dict), make adapters that exist on that side only (depending on Z height differences)
    else, make a wall on that block facing that direction
    repeat for all blocks"""

    Hill_Resolution = 0.7
    Noise_Size = 25

    # Noise Parameters
    width = Noise_Size * (Extents[1] - Extents[0] + 1)
    height = Noise_Size * (Extents[3] - Extents[2] + 1)
    scale = Noise_Size / Hill_Resolution
    octaves_list = [1, 2, 16]
    persistence = 0.2
    lacunarity = 4
    seed = random.randint(1, 100)

    # Generate layers of Perlin noise
    layers = [
        noisetest.generate_perlin_noise(
            width, height, scale, octaves, persistence, lacunarity, seed
        )
        for octaves in octaves_list
    ]

    elapsed = tools.display_time(tools.click("submodule"))
    print("Perlin Noise complete in " + elapsed)

    heightmap_scale_x = 4080 * (Extents[1] - Extents[0] + 1)
    heightmap_scale_y = 4080 * (Extents[3] - Extents[2] + 1)
    heightmap_shift_x = 4080 * Extents[0]
    heightmap_shift_y = 4080 * Extents[2]

    # height of the shortest tree is 400, 1808 internal height off displacement
    scaled_heightmap = noisetest.rescale_heightmap(layers[2], 0, 1808 - 400)

    finalheightmap = cut_and_fill_heightmap(
        scaled_heightmap,
        heightmap_scale_x,
        heightmap_shift_x,
        heightmap_scale_y,
        heightmap_shift_y,
    )

    layers[2] = finalheightmap

    # if FancyDisplay:
    # noisetest.display_perlin_layers(layers)

    ContourMap = {
        "map": finalheightmap,
        "x_scale": heightmap_scale_x,
        "x_shift": heightmap_shift_x,
        "y_scale": heightmap_scale_y,
        "y_shift": heightmap_shift_y,
    }

    elapsed = tools.display_time(tools.click("submodule"))
    print("Contours done in " + elapsed)

    for fill in Blocks:

        Brushes += vmfpy.block(fill[0], fill[1], fill[2])
        Disps = vmfpy.displacements(fill[0], fill[1], fill[2])
        for Entry in Disps:
            Entry += [
                displacement_build(
                    Entry[0], Entry[1], Entry[2], Entry[3], Entry[4], Entry[5]
                )
            ]
        Brushes += Disps

    elapsed = tools.display_time(tools.click("submodule"))
    print("Brushes and Displacements done in " + elapsed)

    EdgeBoundary = 170  # don't put trees in the walls

    Entities += distribute(
        (
            (Extents[0] * 4080, (Extents[1] + 1) * 4080),
            (Extents[2] * 4080, (Extents[3] + 1) * 4080),
        ),
        [
            "models/props_foliage/tree_pine_extrasmall_snow.mdl",
            "models/props_foliage/tree_pine_small_snow.mdl",
            "models/props_foliage/tree_pine_huge_snow.mdl",
        ],
        110,
        len(Blocks) * 125,  # count
    )

    elapsed = tools.display_time(tools.click("submodule"))
    print("Scattering complete in " + elapsed)

    vmfpy.write_to_vmf(Brushes, Entities)

    elapsed = tools.display_time(tools.click("total"))
    print("Railmancer Finished in " + elapsed)


if __name__ == "__main__":
    main()
