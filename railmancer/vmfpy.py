import os, re
from railmancer import vmfpy

# Interface between VMFs as a file type and the system of blocks, entities, etc. Intended to be generic.


def add_brush(Brush):

    global Brushes

    try:

        Brushes += [Brush]

    except:

        Brushes = [Brush]


def add_brush_entity(Object):

    global Brush_Entites

    try:

        Brush_Entites += [Object]

    except:

        Brush_Entites = [Object]


def re_id(original_string, replacement):

    # looking for "id" "00000" where the zeroes are any number
    pattern = r'"id" "\d+"'

    replacement_string = f'"id" "{replacement}"'
    return re.sub(pattern, replacement_string, original_string)


def blank_entity(Pos, MDL, Ang):

    return {
        "pos-x": Pos[0],
        "pos-y": Pos[1],
        "pos-z": Pos[2],
        "mdl": MDL,
        "ang-pitch": Ang[0],
        "ang-yaw": Ang[1],
        "ang-roll": Ang[2],
    }


def get_ID():

    global ID
    ID += 1
    return str(ID)


def brush(Brush: list):

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
    Class = ""

    if Brush[6] == "wall":
        Top_Texture = "TOOLS/TOOLSNODRAW"
        Bottom_Texture = "TOOLS/TOOLSNODRAW"
        Negative_X_Texture = "TOOLS/TOOLSNODRAW"
        Positive_X_Texture = "TOOLS/TOOLSNODRAW"
        Positive_Y_Texture = "TOOLS/TOOLSNODRAW"
        Negative_Y_Texture = "TOOLS/TOOLSNODRAW"

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
        Displacement = Brush[8]
        # grassy: cp_mountainlab/nature/groundtograss001
        Top_Texture = Brush[7]
        Bottom_Texture = "TOOLS/TOOLSNODRAW"
        Negative_X_Texture = "TOOLS/TOOLSNODRAW"
        Positive_X_Texture = "TOOLS/TOOLSNODRAW"
        Positive_Y_Texture = "TOOLS/TOOLSNODRAW"
        Negative_Y_Texture = "TOOLS/TOOLSNODRAW"

    elif Brush[6] == "viscluster":
        Top_Texture = "TOOLS/TOOLSTRIGGER"
        Bottom_Texture = "TOOLS/TOOLSTRIGGER"
        Negative_X_Texture = "TOOLS/TOOLSTRIGGER"
        Positive_X_Texture = "TOOLS/TOOLSTRIGGER"
        Positive_Y_Texture = "TOOLS/TOOLSTRIGGER"
        Negative_Y_Texture = "TOOLS/TOOLSTRIGGER"
        Class = '''"classname" "func_viscluster"'''

    else:
        Top_Texture = str(Brush[6])
        Bottom_Texture = str(Brush[6])
        Negative_X_Texture = str(Brush[6])
        Positive_X_Texture = str(Brush[6])
        Positive_Y_Texture = str(Brush[6])
        Negative_Y_Texture = str(Brush[6])

    X_Start = str(Brush[0])
    X_End = str(Brush[1])
    Y_Start = str(Brush[2])
    Y_End = str(Brush[3])
    Z_Start = str(Brush[4])
    Z_End = str(Brush[5])

    VisgroupData = ""
    if len(Brush) > 9:
        VisgroupData = f'\n                    "visgroupid" "{Brush[9]}"'

    return f"""
    {Class}
    solid
    {{
        "id" "{get_ID()}"
        side
         {{
            "id" "{get_ID()}"
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
            "lightmapscale" "128"
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
            "lightmapscale" "128"
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
            "lightmapscale" "128"
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
            "lightmapscale" "128"
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
            "lightmapscale" "128"
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
            "lightmapscale" "128"
            "smoothing_groups" "0"
        }}
        editor
        {{
            "color" "150 150 160"
            "visgroupshown" "1"
            "visgroupautoshown" "1"{VisgroupData}
        }}
    }}"""


def synthesize_entities(Entities):

    EntityString = ""
    global ID

    for Ent in Entities:

        # if Ent.get("raw_entity", False):

        # EntityString += re_id(Ent["raw_entity"], get_ID())
        VisgroupData = ""
        if Ent.get("visgroup"):

            VisgroupData = f'\n                    "visgroupid" "{Ent.get("visgroup")}"'

        if Ent.get("classname", False) == "tp3_switch":

            EntityString += f"""entity
            {{
                "id" "{get_ID()}"
                "classname" "tp3_switch"
                "angles" "{Ent.get("ang-pitch",0)} {Ent.get("ang-yaw",0)} {Ent.get("ang-roll",0)}"
                "animated" "1"
                "collision_dv" "1"
                "collision_mn" "1"
                "derail" "0"
                "disableshadows" "1"
                "gmod_allowtools" "advdupe2 tp3_node_editor tp3_node_chainer tp3_path_configurator"
                "lever" "{Ent.get("lever","misconfigured")}"
                "model" "{Ent.get("mdl","models/props_2fort/frog.mdl")}"
                "skin" "{Ent.get("skin",0)}"
                "origin" "{Ent["pos-x"]} {Ent["pos-y"]} {Ent["pos-z"]}"
                editor
                {{
                    "color" "220 30 220"
                    "visgroupshown" "1"
                    "visgroupautoshown" "1"{VisgroupData}
                    "logicalpos" "[0 0]"
                }}
            }}"""

        elif Ent.get("classname", False) == "tp3_switch_lever_anim":

            EntityString += f"""entity
            {{
                "id" "{get_ID()}"
                "classname" "tp3_switch_lever_anim"
                "angles" "{Ent.get("ang-pitch",0)} {Ent.get("ang-yaw",0)} {Ent.get("ang-roll",0)}"
                "autoreset" "0"
                "autoscan" "0"
                "behavior" "-1"
                "collision_dv" "1"
                "collision_mn" "1"
                "gmod_allowtools" "advdupe2 tp3_node_editor tp3_node_chainer tp3_path_configurator"
                "levertype" "0"
                "locked" "0"
                "model" "{Ent.get("mdl","models/props_2fort/frog.mdl")}"
                "nowire" "0"
                "seq_idle_close" "idle_close"
                "seq_idle_open" "idle_open"
                "seq_throw_close" "throw_close"
                "seq_throw_open" "throw_open"
                "skin" "{Ent.get("skin",0)}"
                "targetname" "{Ent.get("lever","misconfigured")}"
                "targetstate" "0"
                "origin" "{Ent["pos-x"]} {Ent["pos-y"]} {Ent["pos-z"]}"
                editor
                {{
                    "color" "220 30 220"
                    "visgroupshown" "1"
                    "visgroupautoshown" "1"{VisgroupData}
                    "logicalpos" "[0 0]"
                }}
            }}"""

        else:  # implied if you don't recognize the class or prop_static

            Shadows = ""
            if Ent.get("shadows", None) == "noself":
                Shadows = '''"disableselfshadowing" "1"
	                            "disableshadows" "1"'''

            EntityString += f"""entity
            {{
                "id" "{get_ID()}"
                "classname" "prop_static"
                "angles" "{Ent.get("ang-pitch",0)} {Ent.get("ang-yaw",0)} {Ent.get("ang-roll",0)}"
                "fademindist" "-1"
                "fadescale" "1"
                "model" "{Ent.get("mdl","models/props_2fort/frog.mdl")}"
                "skin" "{Ent.get("skin",0)}"
                "solid" "6"
                "origin" "{Ent["pos-x"]} {Ent["pos-y"]} {Ent["pos-z"]}"
                {Shadows}
                "disablevertexlighting" "{Ent.get("disablevertexlighting",0)}"
                editor
                {{
                    "color" "200 200 150"
                    "visgroupshown" "1"
                    "visgroupautoshown" "1"{VisgroupData}
                    "logicalpos" "[0 0]"
                }}
            }}"""

    EntityString += f"""entity
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

    return EntityString


def synthesize_brushes():

    BrushString = ""
    for Brush in Brushes:
        BrushString += brush(Brush)

    return BrushString


def synthesize_brush_entities():

    BrushEntityString = ""
    for Object in Brush_Entites:
        BrushEntityString += f"""\nentity\n{{\n"id" "{get_ID()}"\n{brush(Object)}}}"""

    return BrushEntityString


def floor(block_x: int, block_y: int, block_z: int, sector_size: int):
    add_brush(
        [
            block_x,
            (block_x + sector_size),
            block_y,
            (block_y + sector_size),
            block_z,
            (block_z - 16),
            "floor",
        ]
    )


def ceiling(block_x: int, block_y: int, block_z: int, sector_size: int):
    add_brush(
        [
            block_x,
            (block_x + sector_size),
            block_y,
            (block_y + sector_size),
            (block_z),
            (block_z + 16),
            "ceiling",
        ]
    )


def viscluster(
    block_x: int,
    block_y: int,
    floor_z: int,
    ceiling_z: int,
    sector_size: int,
    standoff: int,
):
    add_brush_entity(
        [
            block_x + standoff,
            (block_x + sector_size) - standoff,
            block_y + standoff,
            (block_y + sector_size) - standoff,
            (floor_z - 16) + standoff,
            (ceiling_z + 16) - standoff,
            "viscluster",
        ]
    )


def wall(
    block_x: int,
    block_y: int,
    block_z: int,
    height: int,
    dir: int,
    sector_size: int,
    type="wall",
):

    dir = dir % 4

    if dir == 1:
        x_min = sector_size - 16
        x_max = sector_size
        y_min = 0
        y_max = sector_size
    elif dir == 0:
        x_min = 0
        x_max = sector_size
        y_min = sector_size - 16
        y_max = sector_size
    elif dir == 3:
        x_min = 0
        x_max = 16
        y_min = 0
        y_max = sector_size
    elif dir == 2:
        x_min = 0
        x_max = sector_size
        y_min = 0
        y_max = 16

    add_brush(
        [
            block_x + x_min,
            block_x + x_max,
            block_y + y_min,
            block_y + y_max,
            block_z,
            height,
            type,
        ]
    )


def write_to_vmf(filename):

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
        visgroup
        {
            "name" "Scatter"
            "visgroupid" "22"
            "color" "234 131 192"
        }
        visgroup
        {
            "name" "Track"
            "visgroupid" "23"
            "color" "234 131 192"
        }
        visgroup
        {
            "name" "Blocks"
            "visgroupid" "24"
            "color" "234 131 192"
        }
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

    BrushString = synthesize_brushes()
    EntityString = synthesize_entities(get_entities())
    BrushEntityString = synthesize_brush_entities()

    content = Start + BrushString + "}" + EntityString + BrushEntityString + End

    directory = "C:/Users/Metaladon/Desktop/Model Data/VMFS/railmancer"
    full_file_path = os.path.join(directory, filename)

    try:
        os.makedirs(directory, exist_ok=True)

        with open(full_file_path, "w", encoding="utf-8") as file:
            file.write(content)
        print(f"File saved successfully: {full_file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


def data_to_dispinfo(raw_displacement, heights, alphas):

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

    X_Start, X_End, Y_Start, Y_End, Z_Start, Z_End = raw_displacement[:6]

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


def add_entity(Ent):

    global Entities

    try:

        Entities += [Ent]

    except:

        Entities = [Ent]


def frog(pos, ang=[0, 0, 0]):

    add_entity(blank_entity(pos, "models/props_2fort/frog.mdl", ang))


def get_entities():

    return Entities
