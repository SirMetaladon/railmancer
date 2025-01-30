import random, math
import heightmap, lines, scatter, wayfinder, tools, vmfpy, parser, sectors, terrain


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

            FirstDistance, _ = lines.distance_to_line(Ent[0][1][0], Ent[0][1][1])
            SecondDistance, _ = lines.distance_to_line(Ent[0][2][0], Ent[0][2][1])

            if FirstDistance > SecondDistance:
                Entities[ID] = Ent[1]
            else:
                Entities[ID] = Ent[2]

    return Entities


def height_sample(real_x, real_y, samples, radius, sector):

    SectorSize = 360 / samples
    Heights = [heightmap.query_height(real_x, real_y, sector)]
    Arm = [radius, 0]

    for Slice in range(samples):

        offset = tools.rot_z(Arm, Slice * SectorSize)

        Example = heightmap.query_height(real_x + offset[0], real_y + offset[1], sector)
        Heights += [Example]

    return Heights


def distribute(min_distance, TotalPoints, Sector):

    EntsOut = []
    Points = scatter.point_generator(
        scatter.density_field, Sector, int(TotalPoints * 2), min_distance
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

            realdist, _ = lines.distance_to_line(Point[0], Point[1])
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

            HeightSamples = height_sample(Point[0], Point[1], 5, StumpSize, Sector)

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


def query_alpha(real_x, real_y, Terrain, sector):

    dist, _ = lines.distance_to_line(real_x, real_y)

    HeightSamples = height_sample(real_x, real_y, 6, 20, sector)

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


def displacement_build(Block, sector):

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
            (heightmap.query_height(position[0], position[1], sector) - Z_End)
            for position in x_layer
        ]
        for x_layer in posgrid
    ]
    # reconfigure this later to check the specific sub-biome data for this exact position
    alphas = [
        [
            query_alpha(position[0], position[1], terrain.get(), sector)
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


def main():

    tools.click("total")
    tools.click("submodule")

    # internally defined globals (lists that need to be accessed, write-only effectively)
    global Entities, Brushes
    Entities = []
    Brushes = []

    CFG = terrain.configuration("config.json")
    TrackBase = ""  # "scan/squamish.vmf"

    Path = []
    Path += [[[2040, -32, 208], "0fw", -90]]
    Path += [
        [[2040 + CFG["Sector_Size"], (CFG["Sector_Size"] * 3) - 32, 208], "0fw", -90]
    ]

    # Beziers, Entities = wayfinder.realize(Path)

    # Step 1: Import line object from a VMF, as well as the track entities themselves.
    Beziers, Entities = parser.import_track(TrackBase)

    # Step 2: Generate KDTree for distance to this line; speeds up later processes compared to doing it manually
    lines.encode_lines(Beziers, CFG["LineFidelity"])
    # these values are stored as global variables in the lines module.

    # Step 2.5: Since the KDTree has been generated, collapse some special decisionmaking for track entities
    Entities = collapse_quantum_switchstands(Entities)

    # Step 4: Build a sector-map from the blocklist. Dict instead of a list; tells you where the walls are. Also contains a map for "what block is next to this one"
    Sectors = sectors.build_sectors("sector_path_random", (0, 0, 1000, 90, 7))

    # Step 5: Builds the Extents and ContourMaps base from the sectors/blocks
    # the large number is the size of the Hammer grid
    heightmap.build_heightmap_base(
        CFG["Sector_Size"],
        CFG["Noise_Size"],
        math.floor(32768 / CFG["Sector_Size"]),
    )

    # lines.display_path(Beziers, Extents)

    elapsed = tools.display_time(tools.click("submodule"))
    print("Bezier generation complete in " + elapsed)

    heightmap.generate_sector_heightmaps(Sectors)

    print(Sectors["0x0x0"])

    elapsed = tools.display_time(tools.click("submodule"))
    print("Sector Generation done in " + elapsed)

    heightmap.cut_and_fill_sector_heightmaps(Sectors)

    elapsed = tools.display_time(tools.click("submodule"))
    print("Contours done in " + elapsed)

    Brushes = []

    for sector in Sectors.items():

        sector_data = sector[1]
        x, y, z = sector_data[0]["x"], sector_data[0]["y"], sector_data[0]["floor"]

        Brushes += vmfpy.create_scenery_block(sector_data)
        Disps = vmfpy.displacements(
            x,
            y,
            z,
            CFG["Disps_Per_Sector"],
            CFG["Biomes"]["hl2_white_forest"]["terrain"].get(
                "ground_texture", "dev/dev_blendmeasure"
            ),
        )
        for Entry in Disps:
            Entry += [displacement_build(Entry, sector_data)]
        Brushes += Disps

    elapsed = tools.display_time(tools.click("submodule"))
    print("Brushes and Displacements done in " + elapsed)

    Terrain = CFG["Biomes"]["hl2_white_forest"]["terrain"]

    """Entities += distribute(
        (
            (Extents[0] * CFG["Sector_Size"], (Extents[1] + 1) * CFG["Sector_Size"]),
            (Extents[2] * CFG["Sector_Size"], (Extents[3] + 1) * CFG["Sector_Size"]),
        ),
        Terrain.get("model_minimum_distance", 110),
        Terrain.get("models_per_sector", 125),  # count
    )"""

    elapsed = tools.display_time(tools.click("submodule"))
    print("Scattering complete in " + elapsed)

    vmfpy.write_to_vmf(
        Brushes, Entities, f"{"railmancer"}_{random.randint(4000,4999)}{".vmf"}"
    )

    elapsed = tools.display_time(tools.click("total"))
    print("Railmancer Finished in " + elapsed)


if __name__ == "__main__":
    print("RAILMANCER ACTIVATED")
    main()
