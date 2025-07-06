import random, math
from railmancer import (
    heightmap,
    lines,
    scatter,
    tools,
    vmfpy,
    parser,
    sectors,
    terrain,
    track,
    entities,
    trackhammer,
    cfg,
)


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

            HeightSamples = heightmap.height_sample(
                Point[0], Point[1], 5, StumpSize, Sector
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


def query_alpha(real_x, real_y, Terrain, sector_data):

    dist, _ = lines.distance_to_line(real_x, real_y, sector_data)

    HeightSamples = heightmap.height_sample(real_x, real_y, 6, 20, sector_data)

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
    NoiseMetric = random.uniform(-0.5, 0.5) * Terrain.get(
        "alpha_from_noise_multiplier", 50
    )
    TerrainMult = Terrain.get("alpha_multiplier", 1)

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
        [(x * scale_x + shift_x, y * scale_y + shift_y, 0) for y in range(9)]
        for x in range(9)
    ]

    heights = [
        [
            heightmap.query_field("height", position, sector) - Z_End
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
    global Brushes
    Brushes = []

    directory = "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    track.build_track_library(directory, ".mdl")

    CFG = cfg.initialize("railmancer/config.json")
    TrackBase = "vmf inputs/giantspiral.vmf"  # "vmf inputs/squamish.vmf"

    Path = []
    Path += [[[2040, -32 - 6000, 500], "0fw", -90, False]]

    trackhammer.start(Path[0], 0)

    # Step 1: Import line object from a VMF, as well as the track entities themselves.
    parser.import_track(TrackBase)

    tools.click("submodule", "Base line data completed")

    # Step 2: Generate KDTree for distance to this line; speeds up later processes compared to doing it manually
    lines.encode_lines(CFG["line_maximum_poll_point_distance"])
    # these values are stored as global variables in the lines module.

    # Step 2.5: Since the KDTree has been generated, collapse some special decisionmaking for track entities
    entities.collapse_quantum_switchstands()

    tools.click("submodule", "Encoding and collapse done")

    # Step 4: Build a sector-map from the blocklist. Dict instead of a list; tells you where the walls are. Also contains a map for "what block is next to this one"
    sectors.initialize()
    sectors.build_fit()
    sectors.link()

    tools.click("submodule", "Sector framework completed")

    sectors.assign_points_to_sectors()

    # Step 5: Builds the Extents and ContourMaps base from the sectors/blocks
    heightmap.generate_sector_heightmaps()

    tools.click("submodule", "Sector Generation done")

    sectors.merge_edges()
    sectors.blur_grids()

    tools.click("submodule", "Smoothed min-max maps done")

    heightmap.cut_and_fill_sector_heightmaps()

    tools.click("submodule", "Contours done")

    Brushes = []

    for sector_data in sectors.get_all().values():

        x, y, z = sector_data["x"], sector_data["y"], sector_data["floor"]

        Brushes += vmfpy.create_scenery_block(sector_data)
        Disps = vmfpy.displacements(
            x,
            y,
            z,
            CFG["Disps_Per_Sector"],
            terrain.get().get("texture_ground", "dev/dev_blendmeasure"),
        )
        for Entry in Disps:
            Entry += [displacement_build(Entry, sector_data)]
        Brushes += Disps

    tools.click("submodule", "Brushes and Displacements done")

    # Terrain = CFG["Biomes"]["hl2_white_forest"]["terrain"]

    """Entities += distribute(
        (
            (Extents[0] * CFG["sector_real_size"], (Extents[1] + 1) * CFG["sector_real_size"]),
            (Extents[2] * CFG["sector_real_size"], (Extents[3] + 1) * CFG["sector_real_size"]),
        ),
        Terrain.get("model_minimum_distance", 110),
        Terrain.get("models_per_sector", 125),  # count
    )"""

    tools.click("submodule", "Scattering complete")

    vmfpy.write_to_vmf(Brushes, f"{"railmancer"}_{random.randint(4000,4999)}{".vmf"}")

    tools.click("total", "Railmancer Finished")


if __name__ == "__main__":
    print("RAILMANCER ACTIVATED")
    main()
