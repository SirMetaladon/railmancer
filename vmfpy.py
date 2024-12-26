import os, random


def add_entity(Pos, MDL, Ang):

    return {
        "pos-x": Pos[0],
        "pos-y": Pos[1],
        "pos-z": Pos[2],
        "mdl": MDL,
        "ang-pitch": Ang[0],
        "ang-yaw": Ang[1],
        "ang-roll": Ang[2],
    }


def frog(x, y, z):
    return add_entity([x, y, z], "models/props_2fort/frog.mdl", [0, 0, 0])


def get_ID():

    global ID
    ID += 1
    return str(ID)


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

    Output += f"""entity
{{
	"id" "{get_ID()}"
	"classname" "light_environment"
	"_ambient" "116 113 149 300"
	"_ambientHDR" "-1 -1 -1 1"
	"_AmbientScaleHDR" "1"
	"_light" "255 226 196 500"
	"_lightHDR" "-1 -1 -1 1"
	"_lightscaleHDR" "1"
	"angles" "0 60 0"
	"pitch" "-40"
	"SunSpreadAngle" "0"
	"origin" "0 0 300"
	editor
	{{
		"color" "220 30 220"
		"visgroupid" "77"
		"visgroupshown" "1"
		"visgroupautoshown" "1"
		"logicalpos" "[1500 1500]"
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
        "skyname" "sky_stormfront_01"
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
