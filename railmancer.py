import random, math
import noisetest, curvature, scatter, pathfinder, tools, vmfpy, parser
import numpy as np
from scipy.spatial import KDTree
from scipy.ndimage import gaussian_filter


def collapse_quantum_switchstands(Entities):

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

    return Entities


def encode_sector(X, Y):

    return str(X) + "x" + str(Y)


def get_sector(X, Y):

    return Sectors.get(encode_sector(X, Y), False)


def build_sectors(Blocks):

    global Sectors

    Sectors = {}

    for Entry in Blocks:
        Sectors[encode_sector(Entry[0], Entry[1])] = [(Entry[2], Entry[3])]

    # puts in 4 height values to tell you if nearby sectors are filled too
    # think of it as "is there a wall in this direction, and if so how high is it's floor"

    def probe_sector(x, y):

        Sector = get_sector(x, y)

        if Sector is False:
            return False

        else:
            return Sector[0]

    for Sector in Sectors:

        XCoord = int(Sector.split("x")[0])
        YCoord = int(Sector.split("x")[1])

        Sectors[Sector] += [probe_sector(XCoord + 1, YCoord)]
        Sectors[Sector] += [probe_sector(XCoord, YCoord - 1)]
        Sectors[Sector] += [probe_sector(XCoord - 1, YCoord)]
        Sectors[Sector] += [probe_sector(XCoord, YCoord + 1)]

    return Sectors


def build_blocks(xmin=-4, xmax=3, ymin=-4, ymax=3, height=114):

    grid = [
        [x, y, 0, height] for x in range(xmin, xmax + 1) for y in range(ymin, ymax + 1)
    ]
    return grid


def build_extents(blocklist):

    Extents = [0, 0, 0, 0]
    # x min, x max, y min, y max

    for block in blocklist:
        Extents[0] = min(Extents[0], block[0])
        Extents[1] = max(Extents[1], block[0])
        Extents[2] = min(Extents[2], block[1])
        Extents[3] = max(Extents[3], block[1])

    ContourMaps = {
        "x_scale": CFG["Sector_Size"] * (Extents[1] - Extents[0] + 1),
        "x_shift": CFG["Sector_Size"] * Extents[0],
        "y_scale": CFG["Sector_Size"] * (Extents[3] - Extents[2] + 1),
        "y_shift": CFG["Sector_Size"] * Extents[2],
        "width": CFG["Noise_Size"] * (Extents[1] - Extents[0] + 1),
        "height": CFG["Noise_Size"] * (Extents[3] - Extents[2] + 1),
    }

    return Extents, ContourMaps


def query_height(real_x, real_y):

    virtual_x = (real_x - ContourMaps["x_shift"]) / (ContourMaps["x_scale"])
    virtual_y = (real_y - ContourMaps["y_shift"]) / (ContourMaps["y_scale"])

    height = noisetest.bilinear_interpolation(
        ContourMaps["alpine_snow"], virtual_x, virtual_y
    )

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

    Shortest, idx = LineDistanceTree.query([real_x, real_y])

    if dim == 2:
        return Shortest

    # if dim != 2
    Height = LineDistanceHeights[idx]

    return Shortest, Height


def distribute(bounds, min_distance, TotalPoints):

    EntsOut = []
    Points = scatter.point_generator(
        scatter.density_field, bounds, int(TotalPoints * 2), min_distance, Sectors
    )

    for Point in Points:

        if TotalPoints:
            TotalPoints -= 1

            ModelData = CFG["Biomes"]["alpine_snow"]["models"]
            Choices = list(ModelData.keys())
            Weights = tools.extract(ModelData, Choices, "weight", 0)

            Model = random.choices(Choices, Weights)[0]

            dist = distance_to_line(Point[0], Point[1])

            if (
                dist
                <= CFG["Biomes"]["alpine_snow"]["models"][Model]["exclusion_radius"]
            ):
                continue

            StumpSize = CFG["Biomes"]["alpine_snow"]["models"][Model]["base_radius"]

            HeightSamples = height_sample(Point[0], Point[1], 5, StumpSize)

            ModelSteepnessAllowed = CFG["Biomes"]["alpine_snow"]["models"][Model].get(
                "steepness", 999
            )
            LowestSteepnessAllowed = CFG["Biomes"]["alpine_snow"]["models"][Model].get(
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
        - CFG["Biomes"]["alpine_snow"]["terrain"]["too_steep_alpha"]
    )

    return min(
        min(
            max(
                0,
                (dist)
                / CFG["Biomes"]["alpine_snow"]["terrain"]["ballast_alpha_distance"],
            ),
            1,
        )
        * 255,
        min(255 * OverSteep, 255),
    )


def displacement_build(X_Start, X_End, Y_Start, Y_End, Z_Start, Z_End):

    # 8 multiplier due to the range function below (the power of the displacement is 3, or 2^3 = 8)
    scale_x = (X_Start - X_End) / -8
    scale_y = (Y_Start - Y_End) / 8
    shift_x = X_Start
    shift_y = Y_End

    posgrid = [
        [(x * scale_x + shift_x, y * scale_y + shift_y) for y in range(9)]
        for x in range(9)
    ]

    heights = [
        [(query_height(position[0], position[1]) - Z_Start) for position in x_layer]
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


def generate_heightmap_min_max(ContourMaps):

    MinMap = [
        [0 for _ in range(ContourMaps["height"])] for _ in range(ContourMaps["width"])
    ]
    MaxMap = [
        [0 for _ in range(ContourMaps["height"])] for _ in range(ContourMaps["width"])
    ]

    for virtual_x in range(ContourMaps["width"]):
        for virtual_y in range(ContourMaps["height"]):

            real_x, real_y = realize_position(virtual_x, virtual_y)

            distance, height = distance_to_line(real_x, real_y, 3)

            Sector = get_sector(
                math.floor(real_x / CFG["Sector_Size"]),
                math.floor(real_y / CFG["Sector_Size"]),
            )

            metric = min(
                max(
                    distance
                    - CFG["Biomes"]["alpine_snow"]["terrain"]["track_bias_base"],
                    0,
                )
                / CFG["Biomes"]["alpine_snow"]["terrain"]["track_bias_slope"],
                1,
            )

            top = linterp(
                CFG["Biomes"]["alpine_snow"]["terrain"]["track_max"] + height,
                (Sector[0][1] * 16) - 428,  # lowest tree height
                metric,
            )
            bottom = linterp(
                CFG["Biomes"]["alpine_snow"]["terrain"]["track_min"] + height,
                (Sector[0][0] * 16),
                metric,
            )

            MinMap[virtual_x][virtual_y] = bottom
            MaxMap[virtual_x][virtual_y] = top

    return gaussian_filter(MinMap, sigma=1), gaussian_filter(MaxMap, sigma=1)


def rescale_terrain(heightmap, virtual_x, virtual_y):

    return linterp(
        ContourMaps["max_height"][virtual_x][virtual_y],
        ContourMaps["min_height"][virtual_x][virtual_y],
        heightmap[virtual_x][virtual_y],
    )


def carve_height(initial_height, intended_height, distance):

    # this value is "how far away from intended are you allowed to go"
    deviation = (
        math.pow(
            max(
                0,
                (distance - CFG["Biomes"]["alpine_snow"]["terrain"]["cut_basewidth"])
                / CFG["Biomes"]["alpine_snow"]["terrain"]["cut_scale"],
            ),
            CFG["Biomes"]["alpine_snow"]["terrain"]["cut_power"],
        )
        * CFG["Biomes"]["alpine_snow"]["terrain"]["cut_scale"]
    ) * CFG["Biomes"]["alpine_snow"]["terrain"]["cut_slump"]

    return max(
        min(initial_height, intended_height + deviation), intended_height - deviation
    )


def cut_and_fill_heightmap(heightmap):

    global Entities

    for virtual_x in range(len(heightmap)):
        for virtual_y in range(len(heightmap[0])):

            # converts the normalized position into one rescaled by the height min/max
            scaled = rescale_terrain(heightmap, virtual_x, virtual_y)

            real_x, real_y = realize_position(virtual_x, virtual_y)

            distance, height = distance_to_line(real_x, real_y, 3)

            result = carve_height(
                scaled,
                height + CFG["Biomes"]["alpine_snow"]["terrain"]["cut_base_height"],
                distance,
            )

            # Entities += [vmfpy.frog(real_x, real_y, result)]
            # if the distance is less than the base cut width, search for nearby lines and take the lowest carve distance

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


def configuration(path: str):

    Data = tools.import_json(path)

    try:
        Data["Biomes"]
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
        Data[Entry[0]] = Data.get(Entry[0], Entry[1])

    return Data


def main():

    tools.click("total")
    tools.click("submodule")

    # internally defined globals (lists that need to be accessed, write-only effectively)
    global Entities, Brushes, ContourMaps, Sectors, LineDistanceTree, LineDistanceHeights

    # imported data
    global CFG

    CFG = configuration("config.json")

    # Path = []
    # Path += [[[2040, -32, 208], -90]]
    # Path += [[[2040 + CFG["Sector_Size"], (CFG["Sector_Size"] * 3) - 32, 208], -90]]
    # pathfinder is current nonfunctional until I rebuild it
    # Line, Entities = pathfinder.solve(Path, Sectors)
    # Beziers = curvature.generate_line(Line)

    # Step 1: Import line object from a VMF, as well as the track entities themselves.
    Beziers, Entities = parser.import_track("scan/swirly.vmf")

    # Step 2: Generate KDTree for distance to this line; speeds up later processes compared to doing it manually
    LineDistanceHeights, LineDistanceTree = encode_lines(Beziers, CFG["LineFidelity"])

    # Step 2.5: Since the KDTree has been generated, collapse some special decisionmaking for track entities
    Entities = collapse_quantum_switchstands(Entities)

    # Step 3: Lay out the Block shape, currently done with a simple square.
    Blocks = build_blocks(-1, 2, -1, 2)

    # Step 4: Build a sector-map from the blocklist. Dict instead of a list; tells you where the walls are.
    Sectors = build_sectors(Blocks)

    # Step 5: Builds the Extents and ContourMaps base from the sectors/blocks
    Extents, ContourMaps = build_extents(Blocks)

    # if FancyDisplay:
    # curvature.display_path(Beziers, Extents)

    elapsed = tools.display_time(tools.click("submodule"))
    print("Bezier generation complete in " + elapsed)

    """the plan:
    make a noisemap of the minimum height of the terrain and another for the maximum height based on the lines
    for each biome, generate noisemaps; then adjust them to the master heightmap min/maxes, then cut them
    
    """

    # this needs to happen first, per district, then get rectified between biomes and districts... not sure how I'm going to do that
    ContourMaps["min_height"], ContourMaps["max_height"] = generate_heightmap_min_max(
        ContourMaps
    )

    for Biome in CFG["Biomes"].items():

        base_biome_noisemap = noisetest.generate_perlin_noise(
            ContourMaps["height"],
            ContourMaps["width"],
            CFG["Noise_Size"] / Biome[1]["terrain"]["noise_hill_resolution"],
            Biome[1]["terrain"]["noise_octaves"],
            Biome[1]["terrain"]["noise_persistence"],
            Biome[1]["terrain"]["noise_lacunarity"],
            CFG["Terrain_Seed"],
        )

        normalized_heightmap = noisetest.rescale_heightmap(base_biome_noisemap, 0, 1)

        ContourMaps[Biome[0]] = cut_and_fill_heightmap(normalized_heightmap)

    elapsed = tools.display_time(tools.click("submodule"))
    print("Contours done in " + elapsed)

    Brushes = []

    for fill in Blocks:

        # 114 is standard height for modules
        Brushes += vmfpy.block(fill, get_sector(fill[0], fill[1]))
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
            (Extents[0] * CFG["Sector_Size"], (Extents[1] + 1) * CFG["Sector_Size"]),
            (Extents[2] * CFG["Sector_Size"], (Extents[3] + 1) * CFG["Sector_Size"]),
        ),
        110,
        125 * len(Sectors),  # count
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
