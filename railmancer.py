import random, os, math
import noisetest, curvature, scatter
import numpy as np


def add_entity(Pos, MDL, Ang):
    global Entities

    Entities += [
        {
            "pos-x": Pos[0],
            "pos-y": Pos[1],
            "pos-z": Pos[2],
            "mdl": MDL,
        }
    ]


def get_ID():

    global ID
    ID += 1
    return str(ID)


def query_height(real_x, real_y):

    virtual_x = (real_x - ContourMap["x_shift"]) / (ContourMap["x_scale"])
    virtual_y = (real_y - ContourMap["y_shift"]) / (ContourMap["y_scale"])

    height = noisetest.bilinear_interpolation(ContourMap["map"], virtual_x, virtual_y)

    return height


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
    closest_t = ts[min_index]
    print(closest_t, min_index, distances[0])"""
    # print(closest_t)
    # print(distances[closest_t])
    return Shortest  # distances[closest_t]


def distribute(bounds, models, min_distance, num_dots):

    def flat_field(x, y):
        return 0.5

    EntsOut = []
    Points = scatter.point_generator(flat_field, bounds, num_dots, min_distance)
    # scatter.density_field #need to convert this function into the modular field I thought of
    for Point in Points:

        if distance_to_line(Point[0], Point[1]) <= 300:
            # this needs a per-model lookup table
            # current number is roughly 128 (track width from center) + tree exclusion radius
            continue

        EntsOut += [
            {
                "pos-x": Point[0],
                "pos-y": Point[1],
                "pos-z": query_height(Point[0], Point[1]),
                "mdl": random.choice(models),
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

    # use this for determining slope of bezier later
    virtual_x = (real_x - ContourMap["x_shift"]) / (ContourMap["x_scale"])
    virtual_y = (real_y - ContourMap["y_shift"]) / (ContourMap["y_scale"])

    return min(max(0, (dist) / 3), 255)


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

    """for x_layer in posgrid: #debugging frogs for displacement vertexes
        for pos in x_layer:
            add_entity([pos[0], pos[1], 250], "models/props_2fort/frog.mdl", [0, 0, 0])"""
    # for some reason this is needed... sometimes

    # print(X_Start, Y_Start, Z_Start)

    return f"""			dispinfo
			{{
				"power" "3"
				"startposition" "[{0} {0} {0}]"
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


def solid(Brush: list):

    global ID

    if Brush[0] > Brush[1]:
        Brush.insert(0, Brush[1])
        Brush.pop(2)

    if Brush[2] < Brush[3]:
        Brush.insert(2, Brush[3])
        Brush.pop(4)

    if Brush[4] < Brush[5]:
        Brush.insert(4, Brush[5])
        Brush.pop(6)

    Displacement = ""

    if Brush[6] == "wall":
        Top_Texture = "TOOLS/TOOLSNODRAW"
        Bottom_Texture = "TOOLS/TOOLSNODRAW"
        Negative_X_Texture = "tools/toolsskybox"
        Positive_X_Texture = "tools/toolsskybox"
        Positive_Y_Texture = "tools/toolsskybox"
        Negative_Y_Texture = "tools/toolsskybox"

    elif Brush[6] == "ceiling":
        Top_Texture = "TOOLS/TOOLSNODRAW"
        Bottom_Texture = "tools/toolsskybox"
        Negative_X_Texture = "tools/toolsskybox"
        Positive_X_Texture = "tools/toolsskybox"
        Positive_Y_Texture = "tools/toolsskybox"
        Negative_Y_Texture = "tools/toolsskybox"

    elif Brush[6] == "floor":
        Top_Texture = "TOOLS/TOOLSNODRAW"
        Bottom_Texture = "TOOLS/TOOLSNODRAW"
        Negative_X_Texture = "TOOLS/TOOLSNODRAW"
        Positive_X_Texture = "TOOLS/TOOLSNODRAW"
        Positive_Y_Texture = "TOOLS/TOOLSNODRAW"
        Negative_Y_Texture = "TOOLS/TOOLSNODRAW"

    elif Brush[6] == "displacement":
        Displacement = Brush[7]
        # snowy: nature/blendgroundtosnow001
        # grassy: cp_mountainlab/nature/groundtograss001
        Top_Texture = "nature/blendgroundtosnow001"
        Bottom_Texture = "TOOLS/TOOLSNODRAW"
        Negative_X_Texture = "TOOLS/TOOLSNODRAW"
        Positive_X_Texture = "TOOLS/TOOLSNODRAW"
        Positive_Y_Texture = "TOOLS/TOOLSNODRAW"
        Negative_Y_Texture = "TOOLS/TOOLSNODRAW"

    X_Start = str(Brush[0])
    X_End = str(Brush[1])
    Y_Start = str(Brush[2])
    Y_End = str(Brush[3])
    Z_Start = str(Brush[4])
    Z_End = str(Brush[5])

    return f"""
    solid
    {{
        "id" "{get_ID()}"
        side
         {{
            "id" "1"
            "plane" "({X_Start} {Y_Start} {Z_Start}) ({X_End} {Y_Start} {Z_Start}) ({X_End} {Y_End} {Z_Start})"
            vertices_plus
            {{
                "v" "{X_Start} {Y_Start} {Z_Start}"
                "v" "{X_End} {Y_Start} {Z_Start}"
                "v" "{X_End} {Y_End} {Z_Start}"
                "v" "{X_Start} {Y_End} {Z_Start}"
            }}
            "material" "{Top_Texture}"
            "uaxis" "[1 0 0 -0] 0.25"
            "vaxis" "[0 -1 0 128] 0.25"
            "rotation" "0"
            "lightmapscale" "16"
            "smoothing_groups" "0"{Displacement}
        }}
        side
        {{
            "id" "{get_ID()}"
            "plane" "({X_Start} {Y_End} {Z_End}) ({X_End} {Y_End} {Z_End}) ({X_End} {Y_Start} {Z_End})"
            vertices_plus
            {{
                "v" "{X_Start} {Y_End} {Z_End}"
                "v" "{X_End} {Y_End} {Z_End}"
                "v" "{X_End} {Y_Start} {Z_End}"
                "v" "{X_Start} {Y_Start} {Z_End}"
            }}
            "material" "{Bottom_Texture}"
            "uaxis" "[-1 0 0 0] 0.25"
            "vaxis" "[0 -1 0 -0] 0.25"
            "rotation" "0"
            "lightmapscale" "16"
            "smoothing_groups" "0"
        }}
        side
        {{
            "id" "{get_ID()}"
            "plane" "({X_Start} {Y_Start} {Z_Start}) ({X_Start} {Y_End} {Z_Start}) ({X_Start} {Y_End} {Z_End})"
            vertices_plus
            {{
                "v" "{X_Start} {Y_Start} {Z_Start}"
                "v" "{X_Start} {Y_End} {Z_Start}"
                "v" "{X_Start} {Y_End} {Z_End}"
                "v" "{X_Start} {Y_Start} {Z_End}"
            }}
            "material" "{Negative_X_Texture}"
            "uaxis" "[0 -1 0 -0] 0.25"
            "vaxis" "[0 0 -1 0] 0.25"
            "rotation" "0"
            "lightmapscale" "16"
            "smoothing_groups" "0"
        }}
        side
        {{
            "id" "{get_ID()}"
            "plane" "({X_End} {Y_Start} {Z_End}) ({X_End} {Y_End} {Z_End}) ({X_End} {Y_End} {Z_Start})"
            vertices_plus
            {{
                "v" "{X_End} {Y_Start} {Z_End}"
                "v" "{X_End} {Y_End} {Z_End}"
                "v" "{X_End} {Y_End} {Z_Start}"
                "v" "{X_End} {Y_Start} {Z_Start}"
            }}
            "material" "{Positive_X_Texture}"
            "uaxis" "[0 1 0 0] 0.25"
            "vaxis" "[0 0 -1 0] 0.25"
            "rotation" "0"
            "lightmapscale" "16"
            "smoothing_groups" "0"
        }}
        side
        {{
            "id" "{get_ID()}"
            "plane" "({X_End} {Y_Start} {Z_Start}) ({X_Start} {Y_Start} {Z_Start}) ({X_Start} {Y_Start} {Z_End})"
            vertices_plus
            {{
                "v" "{X_End} {Y_Start} {Z_Start}"
                "v" "{X_Start} {Y_Start} {Z_Start}"
                "v" "{X_Start} {Y_Start} {Z_End}"
                "v" "{X_End} {Y_Start} {Z_End}"
            }}
            "material" "{Positive_Y_Texture}"
            "uaxis" "[-1 0 0 0] 0.25"
            "vaxis" "[0 0 -1 0] 0.25"
            "rotation" "0"
            "lightmapscale" "16"
            "smoothing_groups" "0"
        }}
        side
        {{
            "id" "{get_ID()}"
            "plane" "({X_End} {Y_End} {Z_End}) ({X_Start} {Y_End} {Z_End}) ({X_Start} {Y_End} {Z_Start})"
            vertices_plus
            {{
                "v" "{X_End} {Y_End} {Z_End}"
                "v" "{X_Start} {Y_End} {Z_End}"
                "v" "{X_Start} {Y_End} {Z_Start}"
                "v" "{X_End} {Y_End} {Z_Start}"
            }}
            "material" "{Negative_Y_Texture}"
            "uaxis" "[1 0 0 -0] 0.25"
            "vaxis" "[0 0 -1 0] 0.25"
            "rotation" "0"
            "lightmapscale" "16"
            "smoothing_groups" "0"
        }}
        editor
        {{
            "color" "150 150 160"
            "visgroupshown" "1"
            "visgroupautoshown" "1"
        }}
    }}"""


def synthesize_entities(Entities):

    Output = ""
    global ID

    for Ent in Entities:

        Output += f"""entity
        {{
            "id" "{get_ID()}"
            "classname" "{Ent.get("type","prop_static")}"
            "angles" "{Ent.get("ang-pitch",0)} {Ent.get("ang-yaw",0)} {Ent.get("ang-roll",0)}"
            "fademindist" "-1"
            "fadescale" "1"
            "model" "{Ent.get("mdl","models/trakpak3_rsg/straights/s0512_0fw_0pg_+0512x00000x0000.mdl")}"
            "skin" "0"
            "solid" "6"
            "origin" "{Ent["pos-x"]} {Ent["pos-y"]} {Ent["pos-z"]}"
            editor
            {{
                "color" "255 255 0"
                "visgroupshown" "1"
                "visgroupautoshown" "1"
                "logicalpos" "[0 0]"
            }}
        }}"""

    return Output


def synthesize_brushes(Brushes):

    global ID

    Output = ""
    for Brush in Brushes:
        Output += solid(Brush)

    Output += "}"

    return Output


def floor(block_x: int, block_y: int, block_z: int):
    return [
        block_x * 16 * 255,
        (block_x + 1) * 16 * 255,
        block_y * 16 * 255,
        (block_y + 1) * 16 * 255,
        block_z * 16,
        (block_z - 1) * 16,
        "floor",
    ]


def ceiling(block_x: int, block_y: int, block_z: int):
    return [
        block_x * 16 * 255,
        (block_x + 1) * 16 * 255,
        block_y * 16 * 255,
        (block_y + 1) * 16 * 255,
        (block_z + 114) * 16,
        (block_z + 115) * 16,
        "ceiling",
    ]


def displacements(block_x: int, block_y: int, block_z: int):

    Disps = [
        [
            block_x * 16 * 255,
            (block_x + 1 / 3) * 16 * 255,
            block_y * 16 * 255,
            (block_y + 1 / 3) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
        [
            (block_x + 1 / 3) * 16 * 255,
            (block_x + 2 / 3) * 16 * 255,
            (block_y + 0) * 16 * 255,
            (block_y + 1 / 3) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
        [
            (block_x + 2 / 3) * 16 * 255,
            (block_x + 1) * 16 * 255,
            (block_y + 0) * 16 * 255,
            (block_y + 1 / 3) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
        [
            block_x * 16 * 255,
            (block_x + 1 / 3) * 16 * 255,
            (block_y + 1 / 3) * 16 * 255,
            (block_y + 2 / 3) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
        [
            (block_x + 1 / 3) * 16 * 255,
            (block_x + 2 / 3) * 16 * 255,
            (block_y + 1 / 3) * 16 * 255,
            (block_y + 2 / 3) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
        [
            (block_x + 2 / 3) * 16 * 255,
            (block_x + 1) * 16 * 255,
            (block_y + 1 / 3) * 16 * 255,
            (block_y + 2 / 3) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
        [
            block_x * 16 * 255,
            (block_x + 1 / 3) * 16 * 255,
            (block_y + 2 / 3) * 16 * 255,
            (block_y + 1) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
        [
            (block_x + 1 / 3) * 16 * 255,
            (block_x + 2 / 3) * 16 * 255,
            (block_y + 2 / 3) * 16 * 255,
            (block_y + 1) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
        [
            (block_x + 2 / 3) * 16 * 255,
            (block_x + 1) * 16 * 255,
            (block_y + 2 / 3) * 16 * 255,
            (block_y + 1) * 16 * 255,
            (block_z) * 16,
            (block_z + 1) * 16,
            "displacement",
        ],
    ]

    for Entry in Disps:
        Entry += [
            displacement_build(
                Entry[0], Entry[1], Entry[2], Entry[3], Entry[4], Entry[5]
            )
        ]

    return Disps


def wall(block_x: int, block_y: int, block_z: int, dir: int):

    dir = dir % 4

    if dir == 0:
        x_min = 254
        x_max = 255
        y_min = 0
        y_max = 255
    elif dir == 1:
        x_min = 0
        x_max = 255
        y_min = 254
        y_max = 255
    elif dir == 2:
        x_min = 0
        x_max = 1
        y_min = 0
        y_max = 255
    elif dir == 3:
        x_min = 0
        x_max = 255
        y_min = 0
        y_max = 1

    return [
        255 * 16 * block_x + x_min * 16,
        255 * 16 * block_x + x_max * 16,
        255 * 16 * block_y + y_min * 16,
        255 * 16 * block_y + y_max * 16,
        16 * block_z,
        16 * block_z + 114 * 16,
        "wall",
    ]


def block(block_x, block_y, block_z):
    return [
        floor(block_x, block_y, block_z),
        wall(block_x, block_y, block_z, 0),
        wall(block_x, block_y, block_z, 1),
        wall(block_x, block_y, block_z, 2),
        wall(block_x, block_y, block_z, 3),
        ceiling(block_x, block_y, block_z),
    ]


def write_to_vmf(Brushes: list, Entities: list):

    global ID
    ID = 1000

    Start = """versioninfo
    {
        "editorversion" "400"
        "editorbuild" "8868"
        "mapversion" "4"
        "formatversion" "100"
        "prefab" "0"
    }
    visgroups
    {
    }
    viewsettings
    {
        "bSnapToGrid" "1"
        "bShowGrid" "1"
        "bShowLogicalGrid" "0"
        "nGridSpacing" "32"
    }
    palette_plus
    {
        "color0" "255 255 255"
        "color1" "255 255 255"
        "color2" "255 255 255"
        "color3" "255 255 255"
        "color4" "255 255 255"
        "color5" "255 255 255"
        "color6" "255 255 255"
        "color7" "255 255 255"
        "color8" "255 255 255"
        "color9" "255 255 255"
        "color10" "255 255 255"
        "color11" "255 255 255"
        "color12" "255 255 255"
        "color13" "255 255 255"
        "color14" "255 255 255"
        "color15" "255 255 255"
    }
    colorcorrection_plus
    {
        "name0" ""
        "weight0" "1"
        "name1" ""
        "weight1" "1"
        "name2" ""
        "weight2" "1"
        "name3" ""
        "weight3" "1"
    }
    light_plus
    {
        "samples_sun" "6"
        "samples_ambient" "40"
        "samples_vis" "256"
        "texlight" ""
        "incremental_delay" "0"
        "bake_dist" "1024"
        "radius_scale" "1"
        "brightness_scale" "1"
        "ao_scale" "0"
        "bounced" "1"
        "incremental" "1"
        "supersample" "0"
        "bleed_hack" "1"
        "soften_cosine" "0"
        "debug" "0"
        "cubemap" "1"
    }
    postprocess_plus
    {
        "enable" "1"
        "copied_from_controller" "1"
        "bloom_scale" "1"
        "bloom_exponent" "2.5"
        "bloom_saturation" "1"
        "auto_exposure_min" "0.5"
        "auto_exposure_max" "2"
        "tonemap_percent_target" "60"
        "tonemap_percent_bright_pixels" "2"
        "tonemap_min_avg_luminance" "3"
        "tonemap_rate" "1"
        "vignette_enable" "0"
        "vignette_start" "1"
        "vignette_end" "2"
        "vignette_blur" "0"
    }
    bgimages_plus
    {
    }
    world
    {
        "id" "1"
        "mapversion" "4"
        "classname" "worldspawn"
        "detailmaterial" "detail/detailsprites"
        "detailvbsp" "detail.vbsp"
        "maxpropscreenwidth" "-1"
        "skyname" "sky_badlands_01"
        """

    End = """
    cameras
    {
        "activecamera" "-1"
    }
    cordons
    {
        "active" "0"
    }"""

    BrushString = synthesize_brushes(Brushes)
    EntityString = synthesize_entities(Entities)

    content = Start + BrushString + EntityString + End

    directory = "C:/Users/Metaladon/Desktop/Model Data/VMFS/railmancer"
    full_file_path = os.path.join(
        directory, f"{"railmancer"}_{random.randint(2000,2999)}{".vmf"}"
    )

    try:
        os.makedirs(directory, exist_ok=True)

        with open(full_file_path, "w", encoding="utf-8") as file:
            file.write(content)
        print(f"File saved successfully: {full_file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


def carve_height(initial_height, intended_height, distance):

    # how far out the curve starts - think flat area under the track before the cut/fill starts
    offset = 300

    # curve shape - goes from 1 (flat slope) to inf (really steep and agressive)
    power = 1.3

    # this controls the height of a 1-doubling for that power; think scale 10 on power 2 = the curve intersects at dist = 20, clamp = 40
    scale = 30

    # this value scales it down a bit so it's not so steep on a 45 degree angle
    slump = 0.9

    # this value is "how far away from intended are you allowed to go"
    deviation = (math.pow(max(0, (distance - offset) / scale), power) * scale) * slump

    return max(
        min(initial_height, intended_height + deviation), intended_height - deviation
    )


def cut_and_fill_heightmap(heightmap, scale_x, shove_x, scale_y, shove_y):

    Size = len(heightmap)

    for virtual_x in range(Size):
        for virtual_y in range(Size):

            real_x = (virtual_x / Size) * scale_x + shove_x
            real_y = (virtual_y / Size) * scale_y + shove_y

            distance = distance_to_line(real_x, real_y)

            result = carve_height(heightmap[virtual_x][virtual_y], 168, distance)

            heightmap[virtual_x][virtual_y] = result

    return heightmap


def main():

    global Entities, ContourMap, Line, Beziers, Brushes

    Brushes = []
    Entities = []

    # """# right curve
    Line = [
        [np.array([2040, -16, 0]), [0, 1]],
        [np.array([2040, 16, 0]), [0, 1]],
        [np.array([4080 - 16, 2040, 0]), [1, 0]],
        [np.array([4080 + 16, 2040, 0]), [1, 0]],
        [np.array([4080 + 16 + 2048, 2040 + 2048, 0]), [0, 1]],
        [np.array([4080 + 16 + 2048 + 2048, 2040 + 2048 + 2048, 0]), [1, 0]],
    ]  # """

    """ #straight hill
    Line = [
        [np.array([2040, -32, 0]), [0, 1]],
        [np.array([2040, 32, 0]), [0, 1]],
        [np.array([2040, -32 + 4080, -48]), [0, 1]],
        [np.array([2040, 32 + 4080, -48]), [0, 1]],
    ]  # """

    Beziers = curvature.generate_line(Line)

    print(Beziers)

    """rough pseudocode for converting between blocklists and module outputs

    for every incoming block-grid coordinates:

    place a floor and ceiling at the correct height
    populate a dict with the coordinates in x+" "y format with the Z value of that block

    scan the contents of the dict and request all 4 pairs of that block + the surrounding blocks

    if that pair exists (meaning that both coordinates show up in the dict), make adapters that exist on that side only (depending on Z height differences)
    else, make a wall on that block facing that direction
    repeat for all blocks"""

    # Noise Parameters
    width = 60
    height = 60
    scale = 30.0
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

    heightmap_scale_x = 4080 * 2
    heightmap_scale_y = 4080 * 2
    heightmap_shift_x = 0
    heightmap_shift_y = 0

    scaled_heightmap = noisetest.rescale_heightmap(layers[2], -500, 1500)

    finalheightmap = cut_and_fill_heightmap(
        scaled_heightmap,
        heightmap_scale_x,
        heightmap_shift_x,
        heightmap_scale_y,
        heightmap_shift_y,
    )

    layers[2] = finalheightmap

    # noisetest.display_perlin_layers(layers)

    ContourMap = {
        "map": finalheightmap,
        "x_scale": heightmap_scale_x,
        "x_shift": heightmap_shift_x,
        "y_scale": heightmap_scale_y,
        "y_shift": heightmap_shift_y,
    }

    Brushes += block(0, 0, 0)
    Brushes += displacements(0, 0, 0)

    Brushes += block(0, 1, 0)
    Brushes += displacements(0, 1, 0)
    Brushes += block(1, 0, 0)
    Brushes += displacements(1, 0, 0)
    Brushes += block(1, 1, 0)
    Brushes += displacements(1, 1, 0)

    Entities += [
        {
            "pos-x": 2040,
            "pos-y": -32,
            "pos-z": 192 + 16,
            "mdl": "models/trakpak3_rsg/straights/s0064_0fw_0pg_+0064x00000x0000.mdl",
            "ang-yaw": -90,
        },
        {
            "pos-x": 2040,
            "pos-y": 32,
            "pos-z": 192 + 16,
            "mdl": "models/trakpak3_rsg/arcs/r2048/a0fw_8rt_right_0pg_+2048x+2048x0000.mdl",
            "ang-yaw": -90,
        },
        {
            "pos-x": 2040 + 2048,
            "pos-y": 32 + 2048,
            "pos-z": 192 + 16,
            "mdl": "models/trakpak3_rsg/arcs/r2048/a0fw_8lt_left_0pg_+2048x-2048x0000.mdl",
            "ang-yaw": -90 - 90,
        },
        {
            "pos-x": 2040 + 2048 + 2048,
            "pos-y": 32 + 2048 + 2048,
            "pos-z": 192 + 16,
            "mdl": "models/trakpak3_rsg/arcs/r2048/a0fw_8rt_right_0pg_+2048x+2048x0000.mdl",
            "ang-yaw": -90 + 90 - 90,
        },
    ]

    EdgeBoundary = 150  # don't put trees in the walls
    Entities += distribute(
        (
            (EdgeBoundary, heightmap_scale_x - EdgeBoundary),
            (EdgeBoundary, heightmap_scale_y - EdgeBoundary),
        ),
        [
            "models/props_foliage/tree_pine_extrasmall_snow.mdl",
            "models/props_foliage/tree_pine_small_snow.mdl",
            "models/props_foliage/tree_pine_huge_snow.mdl",
        ],
        110,  # minimum distance
        150 * 4,  # count
    )

    write_to_vmf(Brushes, Entities)


if __name__ == "__main__":
    main()
