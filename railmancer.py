import random, math
import noisetest, curvature, scatter, pathfinder, tools, vmfpy, parser
import numpy as np
from scipy.spatial import KDTree


def build_blocks(xmin, xmax, ymin, ymax):

    grid = [[x, y, 0] for x in range(xmin, xmax + 1) for y in range(ymin, ymax + 1)]
    return grid


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

    SectorSize = 360 / samples
    Heights = [query_height(real_x, real_y)]
    Arm = [radius, 0]

    for Slice in range(samples):

        offset = tools.rot_z(Arm, Slice * SectorSize)

        Example = query_height(real_x + offset[0], real_y + offset[1])
        Heights += [Example]

    return Heights


def distance_to_line(real_x, real_y, dim=2):

    Shortest, idx = line_distance_tree.query([real_x, real_y])

    if dim == 2:
        return Shortest

    # if dim != 2
    Height = line_distance_heights[idx]

    return Shortest, Height


def distribute(bounds, min_distance, num_dots):

    TotalPoints = num_dots * len(Blocks)

    EntsOut = []
    Points = scatter.point_generator(
        scatter.density_field, bounds, int(TotalPoints * 2), min_distance, Sectors
    )

    for Point in Points:

        if TotalPoints:
            TotalPoints -= 1

            ModelData = Biomes["alpine_snow"]["models"]
            Choices = list(ModelData.keys())
            Weights = tools.extract(ModelData, Choices, "weight", 0)

            Model = random.choices(Choices, Weights)[0]

            dist = distance_to_line(Point[0], Point[1])

            if dist <= Biomes["alpine_snow"]["models"][Model]["exclusion_radius"]:
                continue

            StumpSize = Biomes["alpine_snow"]["models"][Model]["base_radius"]

            HeightSamples = height_sample(Point[0], Point[1], 5, StumpSize)

            ModelSteepnessAllowed = Biomes["alpine_snow"]["models"][Model].get(
                "steepness", 999
            )
            LowestSteepnessAllowed = Biomes["alpine_snow"]["models"][Model].get(
                "min_steep", -999
            )

            CurrentSteepness = (max(HeightSamples) - min(HeightSamples)) / (
                StumpSize * 2
            )

            if CurrentSteepness > ModelSteepnessAllowed:
                continue
            if CurrentSteepness < LowestSteepnessAllowed:
                continue

            EntsOut += [
                {
                    "pos-x": Point[0],
                    "pos-y": Point[1],
                    "pos-z": min(HeightSamples),
                    "mdl": Model,
                    "ang-yaw": random.randrange(-180, 180),
                    "ang-pitch": random.randrange(-4, 4),
                    "ang-roll": random.randrange(-4, 4),
                    "shadows": "noself",
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

    OverSteep = 1 - (
        ((max(HeightSamples) - min(HeightSamples)) / (40))
        - Biomes["alpine_snow"]["terrain"]["too_steep_alpha"]
    )

    return min(
        min(
            max(0, (dist) / Biomes["alpine_snow"]["terrain"]["ballast_alpha_distance"]),
            1,
        )
        * 255,
        min(255 * OverSteep, 255),
    )


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


def rescale_terrain(initial_height, distance, height):

    metric = (
        min(
            max(distance - Biomes["alpine_snow"]["terrain"]["track_bias_base"], 0),
            Biomes["alpine_snow"]["terrain"]["track_bias_slope"],
        )
        / Biomes["alpine_snow"]["terrain"]["track_bias_slope"]
    )

    top = linterp(
        Biomes["alpine_snow"]["terrain"]["track_max"] + height,
        Biomes["alpine_snow"]["terrain"]["bias_max"],
        metric,
    )
    bottom = linterp(
        Biomes["alpine_snow"]["terrain"]["track_min"] + height,
        Biomes["alpine_snow"]["terrain"]["bias_min"],
        metric,
    )

    depth = top - bottom

    return (initial_height * depth) + bottom


def carve_height(initial_height, intended_height, distance):

    # this value is "how far away from intended are you allowed to go"
    deviation = (
        math.pow(
            max(
                0,
                (distance - Biomes["alpine_snow"]["terrain"]["cut_basewidth"])
                / Biomes["alpine_snow"]["terrain"]["cut_scale"],
            ),
            Biomes["alpine_snow"]["terrain"]["cut_power"],
        )
        * Biomes["alpine_snow"]["terrain"]["cut_scale"]
    ) * Biomes["alpine_snow"]["terrain"]["cut_slump"]

    return max(
        min(initial_height, intended_height + deviation), intended_height - deviation
    )


def cut_and_fill_heightmap(heightmap, scale_x, shove_x, scale_y, shove_y):

    for virtual_x in range(len(heightmap)):
        for virtual_y in range(len(heightmap[0])):

            real_x = ((virtual_x + 0.5) / len(heightmap)) * scale_x + shove_x
            real_y = ((virtual_y + 0.5) / len(heightmap[0])) * scale_y + shove_y

            distance, height = distance_to_line(real_x, real_y, 3)

            scaled = rescale_terrain(heightmap[virtual_x][virtual_y], distance, height)

            result = carve_height(
                scaled,
                height + Biomes["alpine_snow"]["terrain"]["cut_base_height"],
                distance,
            )
            # 40 is the height of the terrain compared to the origin of the track

            heightmap[virtual_x][virtual_y] = result

    return heightmap


def encode_lines(Beziers, LineFidelity):

    sampled_points = []

    for Subsegment in Beziers:
        ts = np.linspace(
            0, 1, int(np.linalg.norm(Subsegment[0] - Subsegment[3]) / LineFidelity) + 1
        )

        sampled_points += [(curvature.bezier(t, Subsegment, 3)) for t in ts]

    points = [(x, y) for x, y, _ in sampled_points]
    return [val for _, _, val in sampled_points], KDTree(points)


def main():

    tools.click("total")
    tools.click("submodule")

    global Entities, ContourMap, Brushes, Biomes, Blocks, Sectors, line_distance_tree, line_distance_heights

    FancyDisplay = False

    LineFidelity = 25  # average units between sampled points on lines; higher is grainer but faster

    Terrain_Seed = 0  # 0  for random, or you can specify it

    Sector_Size = 4080  # I'd highly reccomend not touching this

    Biomes = {
        "alpine_snow": {
            "models": {
                "models/props_foliage/tree_pine_extrasmall_snow.mdl": {
                    "weight": 15,
                    "exclusion_radius": 250,
                    "base_radius": 55,
                    "steepness": 4 / 5,
                },
                "models/props_foliage/tree_pine_small_snow.mdl": {
                    "weight": 25,
                    "exclusion_radius": 300,
                    "base_radius": 55,
                    "steepness": 4 / 5,
                },
                "models/props_foliage/tree_pine_huge_snow.mdl": {
                    "weight": 35,
                    "exclusion_radius": 350,
                    "base_radius": 75,
                    "steepness": 4 / 5,
                },
                "models/props_forest/rock001.mdl": {
                    "weight": 5,
                    "exclusion_radius": 350,
                    "base_radius": 170,
                    "steepness": 3,
                    "min_steep": 2 / 5,
                },
                "models/props_forest/rock002.mdl": {
                    "weight": 5,
                    "exclusion_radius": 350,
                    "base_radius": 120,
                    "steepness": 3,
                    "min_steep": 2 / 5,
                },
                "models/props_forest/rock003.mdl": {
                    "weight": 5,
                    "exclusion_radius": 350,
                    "base_radius": 140,
                    "steepness": 3,
                    "min_steep": 2 / 5,
                },
                "models/props_forest/rock004.mdl": {
                    "weight": 5,
                    "exclusion_radius": 350,
                    "base_radius": 120,
                    "steepness": 3,
                    "min_steep": 2 / 5,
                },
            },
            "terrain": {
                "track_bias_slope": 3000,
                "track_bias_base": 100,
                "cut_power": 2,  # curve shape - goes from 1 (flat slope) to inf (really steep and agressive)
                "cut_scale": 150,  # this controls the height of a 1-doubling for that power; think scale 10 on power 2 = the curve intersects at dist = 20, clamp = 40
                "cut_basewidth": 250,  # how far out the curve starts - think flat area under the track before the cut/fill starts
                "cut_slump": 0.9,  # this value scales it down a bit so it's not so steep on a 45 degree angle
                "bias_max": 5000,
                "bias_min": -2000,
                "track_max": 60,  # relative to the track
                "track_min": -60,  # relative to the track
                "too_steep_alpha": 3 / 4,
                "ballast_alpha_distance": 400,
                "cut_base_height": -45,  # distance from track origin
                "models_per_sector": 125,
                "noise_hill_resolution": 0.7,
                "noise_size": 25,
                "noise_persistence": 0.2,
                "noise_lacunarity": 4,
                "noise_octaves": 2,
            },
        }
    }

    Blocks = []
    # programmed to be the size of the full map right now
    Blocks += build_blocks(-4, 3, -4, 3)

    Sectors = {}

    for Entry in Blocks:
        # [1, 0, 0]
        Sectors[tools.sector_encode(Entry[0], Entry[1])] = [Entry[2]]

    # puts in 4 booleans to tell you if nearby sectors are filled too
    # think of it as "is there a wall in this direction"
    for Sector in Sectors:

        XCoord = int(Sector.split("x")[0])
        YCoord = int(Sector.split("x")[1])

        Sectors[Sector] += [
            len(Sectors.get(tools.sector_encode(XCoord + 1, YCoord), [])) == 0
        ]
        Sectors[Sector] += [
            len(Sectors.get(tools.sector_encode(XCoord, YCoord - 1), [])) == 0
        ]
        Sectors[Sector] += [
            len(Sectors.get(tools.sector_encode(XCoord - 1, YCoord), [])) == 0
        ]
        Sectors[Sector] += [
            len(Sectors.get(tools.sector_encode(XCoord, YCoord + 1), [])) == 0
        ]

    Extents = bounds(Blocks)

    Brushes = []

    # Path = []
    # Path += [[[2040, -32, 208], -90]]
    # Path += [[[2040 + Sector_Size, (Sector_Size * 3) - 32, 208], -90]]
    # pathfinder is current nonfunctional until I rebuild it
    # Line, Entities = pathfinder.solve(Path, Sectors)
    # Beziers = curvature.generate_line(Line)

    Beziers, Entities = parser.import_track("scan/snowline.vmf")

    if FancyDisplay:
        curvature.display_path(Beziers, Extents)

    line_distance_heights = line_distance_tree = encode_lines(Beziers, LineFidelity)

    for ID in range(len(Entities)):

        Ent = Entities[ID]

        try:
            if Ent[0][0] == "collapse":
                Collapse = 1
            else:
                Collapse = 0
        except:
            Collapse = 0

        if Collapse:

            FirstDistance = distance_to_line(Ent[0][1][0], Ent[0][1][1])
            SecondDistance = distance_to_line(Ent[0][2][0], Ent[0][2][1])

            if FirstDistance > SecondDistance:
                Entities[ID] = Ent[1]
            else:
                Entities[ID] = Ent[2]

    elapsed = tools.display_time(tools.click("submodule"))
    print("Bezier generation complete in " + elapsed)

    """rough pseudocode for converting between blocklists and module outputs

    for every incoming block-grid coordinates:

    place a floor and ceiling at the correct height
    populate a dict with the coordinates in x+" "y format with the Z value of that block

    scan the contents of the dict and request all 4 pairs of that block + the surrounding blocks

    if that pair exists (meaning that both coordinates show up in the dict), make adapters that exist on that side only (depending on Z height differences)
    else, make a wall on that block facing that direction
    repeat for all blocks"""

    heightmap_scale_x = Sector_Size * (Extents[1] - Extents[0] + 1)
    heightmap_scale_y = Sector_Size * (Extents[3] - Extents[2] + 1)
    heightmap_shift_x = Sector_Size * Extents[0]
    heightmap_shift_y = Sector_Size * Extents[2]

    Noise_Library = {}

    for Biome in Biomes.items():

        width = Biome[1]["noise_size"] * (Extents[1] - Extents[0] + 1)
        height = Biome[1]["noise_size"] * (Extents[3] - Extents[2] + 1)
        scale = Biome[1]["noise_size"] / Biome[1]["noise_hill_resolution"]

        perlin_noise = noisetest.generate_perlin_noise(
            width,
            height,
            scale,
            Biome[1]["noise_octaves"],
            Biome[1]["noise_persistence"],
            Biome[1]["noise_lacunarity"],
            random.randint(1, 100) if Terrain_Seed == 0 else Terrain_Seed,
        )

    scaled_heightmap = noisetest.rescale_heightmap(perlin_noise, 0, 1)

    elapsed = tools.display_time(tools.click("submodule"))
    print("Perlin Noise complete in " + elapsed)

    finalheightmap = cut_and_fill_heightmap(
        scaled_heightmap,
        heightmap_scale_x,
        heightmap_shift_x,
        heightmap_scale_y,
        heightmap_shift_y,
    )

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

    Entities += distribute(
        (
            (Extents[0] * Sector_Size, (Extents[1] + 1) * Sector_Size),
            (Extents[2] * Sector_Size, (Extents[3] + 1) * Sector_Size),
        ),
        110,
        125,  # count
    )

    elapsed = tools.display_time(tools.click("submodule"))
    print("Scattering complete in " + elapsed)

    vmfpy.write_to_vmf(
        Brushes, Entities, f"{"railmancer"}_{random.randint(3000,3999)}{".vmf"}"
    )

    elapsed = tools.display_time(tools.click("total"))
    print("Railmancer Finished in " + elapsed)


if __name__ == "__main__":
    print("RAILMANCER ACTIVATED")
    main()
