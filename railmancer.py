import random
import heightmap, lines, scatter, wayfinder, tools, vmfpy, parser, sectors


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

            FirstDistance = lines.distance_to_line(Ent[0][1][0], Ent[0][1][1])
            SecondDistance = lines.distance_to_line(Ent[0][2][0], Ent[0][2][1])

            if FirstDistance > SecondDistance:
                Entities[ID] = Ent[1]
            else:
                Entities[ID] = Ent[2]

    return Entities


def build_blocks(xmin=-4, xmax=3, ymin=-4, ymax=3, bottom=0, top=114):

    # idiot insurance
    floor = min(bottom, top)
    ceiling = max(bottom, top)

    grid = [
        [x, y, floor, ceiling]
        for x in range(xmin, xmax + 1)
        for y in range(ymin, ymax + 1)
    ]
    return grid


def height_sample(real_x, real_y, samples, radius):

    SectorSize = 360 / samples
    Heights = [heightmap.query_height(real_x, real_y)]
    Arm = [radius, 0]

    for Slice in range(samples):

        offset = tools.rot_z(Arm, Slice * SectorSize)

        Example = heightmap.query_height(real_x + offset[0], real_y + offset[1])
        Heights += [Example]

    return Heights


def distribute(bounds, min_distance, TotalPoints):

    EntsOut = []
    Points = scatter.point_generator(
        scatter.density_field, bounds, int(TotalPoints * 2), min_distance
    )

    for Point in Points:

        if TotalPoints:
            TotalPoints -= 1

            ModelData = CFG["Biomes"]["hl2_white_forest"]["models"]
            Choices = list(ModelData.keys())
            Weights = tools.extract(ModelData, Choices, "weight", 0)

            ModelPath = random.choices(Choices, Weights)[0]
            Model = ModelData[ModelPath]

            dist = lines.distance_to_line(Point[0], Point[1])

            if dist <= Model["exclusion_radius"]:
                continue

            StumpSize = Model["base_radius"]

            HeightSamples = height_sample(Point[0], Point[1], 5, StumpSize)

            ModelSteepnessAllowed = Model.get("steepness", 999)
            LowestSteepnessAllowed = Model.get("min_steep", -999)

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
                    "pos-z": min(HeightSamples) + Model.get("height_offset", 0),
                    "mdl": ModelPath,
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


def query_alpha(real_x, real_y, Terrain):

    dist = lines.distance_to_line(real_x, real_y)

    HeightSamples = height_sample(real_x, real_y, 6, 20)

    LocalSlope = (max(HeightSamples) - min(HeightSamples)) / (40)
    SlopeTarget = Terrain.get("alpha_steepness_cutoff", 0.75)
    TransitionLength = Terrain.get("alpha_steepness_transition", 0.75)

    if TransitionLength == 0:
        SlopeMetric = 0 if LocalSlope < SlopeTarget else 1
    else:
        SlopeMetric = 0.5 + (LocalSlope - SlopeTarget) / TransitionLength

    DistanceMetric = (
        max(dist - Terrain.get("ballast_alpha_distance", 96), 0)
        / Terrain.get("ballast_alpha_slope", 200)
    ) * 255
    SteepnessMetric = SlopeMetric * 255
    NoiseMetric = random.uniform(-0.5, 0.5) * Terrain.get("alpha_noise_mult", 50)
    TerrainMult = Terrain.get("disp_alpha_mult", 1)

    BaseAlpha = min(DistanceMetric, SteepnessMetric)
    AdjustedAlpha = tools.scale(BaseAlpha, TerrainMult, 255)

    return tools.clamped(AdjustedAlpha + NoiseMetric, 0, 255)


def displacement_build(Block):

    X_Start, X_End, Y_Start, Y_End, Z_Start, Z_End = Block[:6]

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
        [
            (heightmap.query_height(position[0], position[1]) - Z_End)
            for position in x_layer
        ]
        for x_layer in posgrid
    ]
    # reconfigure this later to check the specific sub-biome data for this exact position
    alphas = [
        [
            query_alpha(
                position[0], position[1], CFG["Biomes"]["hl2_white_forest"]["terrain"]
            )
            for position in x_layer
        ]
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
    global Entities, Brushes
    Entities = []
    Brushes = []

    # imported data
    global CFG

    CFG = configuration("config.json")
    TrackBase = ""

    # Step 3: Lay out the Block shape, currently done with a simple square.
    Blocks = build_blocks(-1, 2, -1, 2)

    # Step 4: Build a sector-map from the blocklist. Dict instead of a list; tells you where the walls are.
    sectors.build_sectors(Blocks)

    Path = []
    Path += [[[2040, -32, 208], "0fw", -90]]
    Path += [
        [[2040 + CFG["Sector_Size"], (CFG["Sector_Size"] * 3) - 32, 208], "0fw", -90]
    ]

    Beziers, Entities = wayfinder.realize(Path)

    # Step 1: Import line object from a VMF, as well as the track entities themselves.
    # Beziers, Entities = parser.import_track(TrackBase)

    # Step 2: Generate KDTree for distance to this line; speeds up later processes compared to doing it manually
    lines.encode_lines(Beziers, CFG["LineFidelity"])
    # these values are stored as global variables in the lines module.

    # Step 2.5: Since the KDTree has been generated, collapse some special decisionmaking for track entities
    Entities = collapse_quantum_switchstands(Entities)

    # Step 5: Builds the Extents and ContourMaps base from the sectors/blocks
    Extents = heightmap.build_heightmap_base(
        Blocks, CFG["Sector_Size"], CFG["Noise_Size"]
    )

    elapsed = tools.display_time(tools.click("submodule"))
    print("Bezier generation complete in " + elapsed)

    """the plan:
    make a noisemap of the minimum height of the terrain and another for the maximum height based on the lines
    for each biome, generate noisemaps; then adjust them to the master heightmap min/maxes, then cut them
    
    """
    # 2 means nothing at the moment, just 2 axies.
    heightmap.generate_test_biomes(2)

    # this needs to happen first, per district, then get rectified between biomes and districts... not sure how I'm going to do that

    heightmap.generate_heightmap_min_max(
        CFG["Sector_Size"], CFG["Biomes"]["hl2_white_forest"]["terrain"]
    )

    heightmap.generate_biome_heightmaps(
        CFG["Biomes"], CFG["Noise_Size"], CFG["Terrain_Seed"]
    )

    elapsed = tools.display_time(tools.click("submodule"))
    print("Contours done in " + elapsed)

    Brushes = []

    for fill in Blocks:

        Brushes += vmfpy.block(fill, sectors.get_sector(fill[0], fill[1]))
        Disps = vmfpy.displacements(
            fill[0],
            fill[1],
            fill[2],
            CFG["Disps_Per_Sector"],
            CFG["Biomes"]["hl2_white_forest"]["terrain"].get(
                "ground_texture", "dev/dev_blendmeasure"
            ),
        )
        for Entry in Disps:
            Entry += [displacement_build(Entry)]
        Brushes += Disps

    elapsed = tools.display_time(tools.click("submodule"))
    print("Brushes and Displacements done in " + elapsed)

    Terrain = CFG["Biomes"]["hl2_white_forest"]["terrain"]

    Entities += distribute(
        (
            (Extents[0] * CFG["Sector_Size"], (Extents[1] + 1) * CFG["Sector_Size"]),
            (Extents[2] * CFG["Sector_Size"], (Extents[3] + 1) * CFG["Sector_Size"]),
        ),
        Terrain.get("model_minimum_distance", 110),
        Terrain.get("models_per_sector", 125) * len(Blocks),  # count
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
