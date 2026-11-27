import bisect
import os, re, math
from railmancer import tools, vmfpy, settings

# Interface between VMFs as a file type and the system of blocks, entities, etc. Intended to be generic.

Brushes: list = []
# Parallel to Brushes. None means the solid is not in a sector group.
Brush_Group_Keys: list = []
# sector id -> group id string, filled when assemble allocates ids.
Sector_Group_IDs: dict = {}
Brush_Entites: list = []
Entities: list = []


# Handler function that makes Brushes a global list.
def add_brush(Brush, group_key=None):

    global Brushes, Brush_Group_Keys

    Flag = 0

    for x in range(0, 5):
        if abs(Brush[x]) > 16384:
            Flag = 1

    if Flag == 0:
        # Tests and callers clear Brushes directly. Drop stale keys with it.
        if not Brushes:
            Brush_Group_Keys = []
        Brushes += [Brush]
        Brush_Group_Keys += [group_key]


def add_entity(Ent):

    global Entities
    Entities += [Ent]


# Handler function that makes Brush Entities a global list.
def add_brush_entity(Object):

    global Brush_Entites

    try:

        Brush_Entites += [Object]

    except:

        Brush_Entites = [Object]


# I don't know if I used this? I think this was related to Regex that handled track VMF functions, but I think I didn't use it.
def re_id(original_string, replacement):

    # looking for "id" "00000" where the zeroes are any number
    pattern = r'"id" "\d+"'

    replacement_string = f'"id" "{replacement}"'
    return re.sub(pattern, replacement_string, original_string)


# Returns a prefilled dictionary with position, model, angle.
def blank_entity(Pos, MDL, Ang):

    return {
        "pos": Pos,
        "mdl": MDL,
        "ang": Ang,
    }


# Iterator that returns an unused ID
def get_ID():

    global ID
    ID += 1
    return str(ID)


# From a list-brush object, compile all the information together to make a brush-string ready for assembly in to the final VMF.
def brush(Brush: list, group_id=None):

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
    GroupLine = ""
    if group_id:
        GroupLine = f'\n            "groupid" "{group_id}"'
    if len(Brush) > 9:
        # Explicit id, including the pathfinding cubes on visgroup 24.
        VisgroupData = f'\n                    "visgroupid" "{resolve_visgroup(Brush[9])}"'
    elif Brush[6] in _TERRAIN_BRUSH_KINDS:
        # Floors, ceilings, sky walls, displacements, visclusters.
        VisgroupData = (
            f'\n                    "visgroupid" "{resolve_visgroup(VISGROUP_TERRAIN)}"'
        )

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
            "color" "150 150 160"{GroupLine}
            "visgroupshown" "1"
            "visgroupautoshown" "1"{VisgroupData}
        }}
    }}"""


def add_light_environment():

    # The input's own sun wins when it is actually in the map. A light that
    # exists only inside hidden { } does not, so Railmancer still adds one.
    if base_map is not None and base_map.visible_light:
        return

    add_entity({"classname": "light_environment"})


# Turns the main list of Entity-list primitives into compiled strings ready for VMF assembly.
def synthesize_entities(Entities):

    EntityString = ""
    global ID

    for Ent in Entities:

        if isinstance(Ent, list):
            # throw out uncollapsed entities (from switch stands, in case of lack of compiling them)
            continue

        # if Ent.get("raw_entity", False):

        # EntityString += re_id(Ent["raw_entity"], get_ID())
        VisgroupData = ""
        if Ent.get("visgroup"):

            VisgroupData = (
                f'\n                    "visgroupid" "{resolve_visgroup(Ent.get("visgroup"))}"'
            )

        if Ent.get("classname", False) == "tp3_switch":

            EntityString += f"""entity
            {{
                "id" "{get_ID()}"
                "classname" "tp3_switch"
                "angles" "{Ent["ang"][0]} {Ent["ang"][1]} {Ent["ang"][2]}"
                "animated" "1"
                "collision_dv" "1"
                "collision_mn" "1"
                "derail" "0"
                "disableshadows" "1"
                "gmod_allowtools" "advdupe2 tp3_node_editor tp3_node_chainer tp3_path_configurator"
                "lever" "{Ent.get("lever","misconfigured")}"
                "model" "{Ent.get("mdl","models/props_2fort/frog.mdl")}"
                "model_div" "{Ent.get("model_div", Ent.get("mdl","models/props_2fort/frog.mdl"))}"
                "skin" "{Ent.get("skin",0)}"
                "origin" "{Ent["pos"][0]} {Ent["pos"][1]} {Ent["pos"][2]}"
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
                "angles" "{Ent["ang"][0]} {Ent["ang"][1]} {Ent["ang"][2]}"
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
                "origin" "{Ent["pos"][0]} {Ent["pos"][1]} {Ent["pos"][2]}"
                editor
                {{
                    "color" "220 30 220"
                    "visgroupshown" "1"
                    "visgroupautoshown" "1"{VisgroupData}
                    "logicalpos" "[0 0]"
                }}
            }}"""

        elif Ent.get("classname", False) == "info_null":

            EntityString += f"""entity
            {{
                "id" "{get_ID()}"
                "classname" "info_null"
                "targetname" "{Ent.get("targetname", "marker")}"
                "origin" "{Ent["pos"][0]} {Ent["pos"][1]} {Ent["pos"][2]}"
                editor
                {{
                    "color" "255 180 40"
                    "visgroupshown" "1"
                    "visgroupautoshown" "1"{VisgroupData}
                    "logicalpos" "[0 0]"
                }}
            }}"""

        elif Ent.get("classname", False) == "info_teleport_destination":

            EntityString += f"""entity
            {{
                "id" "{get_ID()}"
                "classname" "info_teleport_destination"
                "targetname" "{Ent.get("targetname", "warp")}"
                "angles" "{Ent["ang"][0]} {Ent["ang"][1]} {Ent["ang"][2]}"
                "origin" "{Ent["pos"][0]} {Ent["pos"][1]} {Ent["pos"][2]}"
                editor
                {{
                    "color" "255 180 40"
                    "visgroupshown" "1"
                    "visgroupautoshown" "1"{VisgroupData}
                    "logicalpos" "[0 0]"
                }}
            }}"""

        elif Ent.get("classname", False) == "light_environment":
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
                    "visgroupid" "{resolve_visgroup(VISGROUP_LIGHT)}"
                    "visgroupshown" "1"
                    "visgroupautoshown" "1"
                    "logicalpos" "[1500 1500]"
                }}
            }}"""

        else:  # implied if you don't recognize the class or prop_static

            Shadows = ""
            if Ent.get("shadows", None) == "noself":
                Shadows = '''"disableselfshadowing" "1"
	                            "disableshadows" "1"'''

            GroupData = ""
            if Ent.get("groupid"):
                GroupData = f'\n                    "groupid" "{Ent.get("groupid")}"'

            TargetName = ""
            if Ent.get("targetname"):
                TargetName = f'\n                "targetname" "{Ent.get("targetname")}"'

            EntityString += f"""entity
            {{
                "id" "{get_ID()}"
                "classname" "prop_static"
                "angles" "{Ent["ang"][0]} {Ent["ang"][1]} {Ent["ang"][2]}"{TargetName}
                "fademindist" "-1"
                "fadescale" "1"
                "model" "{Ent.get("mdl","models/props_2fort/frog.mdl")}"
                "skin" "{Ent.get("skin",0)}"
                "solid" "6"
                "origin" "{Ent["pos"][0]} {Ent["pos"][1]} {Ent["pos"][2]}"
                {Shadows}
                "disablevertexlighting" "{Ent.get("disablevertexlighting",0)}"
                editor
                {{
                    "color" "200 200 150"
                    "visgroupshown" "1"
                    "visgroupautoshown" "1"{VisgroupData}{GroupData}
                    "logicalpos" "[0 0]"
                }}
            }}"""

    print(f"Synthesized {len(Entities)} entities into {len(EntityString)} chars.")

    return EntityString


# Runs through the global list of brushes and returns the completed brush-string
def synthesize_brushes():

    BrushString = ""
    for index, Brush in enumerate(Brushes):
        key = Brush_Group_Keys[index] if index < len(Brush_Group_Keys) else None
        group_id = Sector_Group_IDs.get(key) if key is not None else None
        BrushString += brush(Brush, group_id)

    print(f"Synthesized {len(Brushes)} brushes into {len(BrushString)} chars.")

    return BrushString


# Runs through the global list of brush-entities and returns the completed VMF string.
def synthesize_brush_entities():

    BrushEntityString = ""
    for Object in Brush_Entites:
        BrushEntityString += f"""\nentity\n{{\n"id" "{get_ID()}"\n{brush(Object)}}}"""

    print(
        f"Synthesized {len(Brush_Entites)} brush-entities into {len(BrushEntityString)} chars."
    )

    return BrushEntityString


# From a set of coordinates and a sector size hint, add the brushe for a floor.
def floor(block_x: int, block_y: int, block_z: int, sector_size: int, group_key=None):
    add_brush(
        [
            block_x,
            (block_x + sector_size),
            block_y,
            (block_y + sector_size),
            block_z,
            (block_z - 16),
            "floor",
        ],
        group_key,
    )


# From a set of coordinates and a sector size hint, add the brush for a ceiling.
def ceiling(block_x: int, block_y: int, block_z: int, sector_size: int, group_key=None):
    add_brush(
        [
            block_x,
            (block_x + sector_size),
            block_y,
            (block_y + sector_size),
            (block_z),
            (block_z + 16),
            "ceiling",
        ],
        group_key,
    )


# From a set of coordinates and a few parameters concerning visclusters specifically, create a brush entity.
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


# From coordinates and a listed height and sector size, create a wall brush with the right handedness for the direction
def wall(
    block_x: int,
    block_y: int,
    block_z: int,
    height: int,
    dir: int,
    sector_size: int,
    type="wall",
    group_key=None,
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
        ],
        group_key,
    )


def _static_prop(entity):
    # Scatter omits classname; synthesize_entities then writes prop_static.
    if not isinstance(entity, dict):
        return False
    kind = entity.get("classname", "prop_static")
    return kind in (None, False, "", "prop_static")


# get_ID() starts at 1000 and counts solids, sides, and entities.
# Group ids live up here so a cell per sector cannot collide with that counter.
GROUP_ID_BASE = 1000000000

# Fresh-file visgroup ids. A loaded input map does not use these numbers:
# assemble_vmf allocates a new id above that file's max visgroupid for each
# one, and resolve_visgroup() rewrites the literals below on the way out.
# 77 is the light_environment editor id. It used to be written with no
# visgroup block; the Light child under Railmancer is that definition.
VISGROUP_SCATTER = "22"
VISGROUP_NEW_TRACK = "23"
VISGROUP_BLOCKS = "24"
VISGROUP_OLD_TRACK = "25"
VISGROUP_TERRAIN = "26"
VISGROUP_SWITCH_STANDS = "27"
VISGROUP_RAILMANCER = "28"
VISGROUP_ORIGINAL = "29"
VISGROUP_MARKERS = "30"
VISGROUP_LIGHT = "77"

# (logical id, Hammer name, parent name or None). Order is the allocation
# order and the order they are written under the parent.
_VISGROUP_SPECS = (
    (VISGROUP_RAILMANCER, "Railmancer", None, "234 131 192"),
    (VISGROUP_SCATTER, "Scatter", "Railmancer", "234 131 192"),
    (VISGROUP_NEW_TRACK, "New Track", "Railmancer", "234 131 192"),
    (VISGROUP_BLOCKS, "Blocks", "Railmancer", "234 131 192"),
    (VISGROUP_TERRAIN, "Terrain", "Railmancer", "234 131 192"),
    (VISGROUP_SWITCH_STANDS, "Switch Stands", "Railmancer", "234 131 192"),
    (VISGROUP_OLD_TRACK, "Old Track", "Railmancer", "234 131 192"),
    (VISGROUP_LIGHT, "Light", "Railmancer", "234 131 192"),
    (VISGROUP_ORIGINAL, "Original", None, "90 140 200"),
    # After Original so a map with no visgroups still gives Original id 9.
    # The writer nests this under Railmancer because of its parent, not its place in the list.
    (VISGROUP_MARKERS, "Markers", "Railmancer", "255 180 40"),
)

# Sector shells and displacements. Pathfinding cubes pass visgroup 24
# explicitly and stay in Blocks; these have no visgroup of their own.
_TERRAIN_BRUSH_KINDS = ("wall", "floor", "ceiling", "displacement", "viscluster")

# Set by parser.import_track when a VMF is loaded. None means "write a
# fresh file", which is also what an empty import path selects.
base_map = None


class _BaseMap:
    """The input VMF, the track-entity spans to drop, and allocated ids."""

    def __init__(self, text, consumed_spans, max_id, max_visgroupid, visible_light, vis_ids):
        self.text = text
        self.consumed_spans = consumed_spans
        self.max_id = max_id
        self.max_visgroupid = max_visgroupid
        self.visible_light = visible_light
        self.vis_ids = vis_ids


def clear_base_map():

    global base_map
    base_map = None


def resolve_visgroup(stored):

    # Railmancer code stores the fresh-file ids ("22" and so on). With no
    # input those are the real ids. With an input they are rewritten to the
    # ids allocated above that file, so Isaiah's own visgroup 22 is left
    # alone and Scatter does not land on it.
    key = str(stored)
    if base_map is None:
        return key
    return base_map.vis_ids.get(key, key)


def _max_quoted_int(text, key):

    numbers = [int(value) for value in re.findall(rf'"{key}"\s+"(\d+)"', text)]
    if not numbers:
        return 0
    return max(numbers)


def _entity_hidden(blocks, index):

    current = blocks[index].parent
    while current is not None:
        if blocks[current].name == "hidden":
            return True
        current = blocks[current].parent
    return False


def _visible_light_environment(text, blocks):

    # "Hidden" here is the hidden { } wrapper. visgroupshown 0 is a
    # different switch: the entity is still the map's sun, so Railmancer
    # must not add a second one.
    for index, block in enumerate(blocks):
        if block.name != "entity" or block.close_brace < 0:
            continue
        body = text[block.start : block.close_brace + 1]
        match = re.search(r'"classname"\s+"([^"]*)"', body)
        if not match or match.group(1) != "light_environment":
            continue
        if _entity_hidden(blocks, index):
            continue
        return True
    return False


def set_base_map(text, consumed_spans):

    """Remember the input file as the document write_to_vmf will extend.

    consumed_spans are (start, end) slices of the entity blocks the parser
    rebuilt. The splicer deletes those and, when a top-level hidden block
    contained nothing else, deletes the wrapper with them.
    """

    global base_map

    from railmancer import vmfparse

    blocks = vmfparse.parse_blocks(text)
    max_visgroupid = _max_quoted_int(text, "visgroupid")
    vis_ids = {}
    next_vis = max_visgroupid + 1
    for logical, _name, _parent, _color in _VISGROUP_SPECS:
        vis_ids[logical] = str(next_vis)
        next_vis += 1

    base_map = _BaseMap(
        text=text,
        consumed_spans=list(consumed_spans),
        max_id=_max_quoted_int(text, "id"),
        max_visgroupid=max_visgroupid,
        visible_light=_visible_light_environment(text, blocks),
        vis_ids=vis_ids,
    )


def _visgroup_block(name, vis_id, children="", indent="        ", color="234 131 192"):

    return (
        f"{indent}visgroup\n"
        f"{indent}{{\n"
        f'{indent}    "name" "{name}"\n'
        f'{indent}    "visgroupid" "{vis_id}"\n'
        f'{indent}    "color" "{color}"\n'
        f"{children}"
        f"{indent}}}\n"
    )


def _format_visgroup_tree(id_of, include_original):

    # Children are nested inside Railmancer so one checkbox hides everything
    # this run added. Original is a sibling: preserved input objects join it
    # by an extra visgroupid line, and Railmancer's own objects do not.
    children = ""
    for logical, name, parent, color in _VISGROUP_SPECS:
        if parent != "Railmancer":
            continue
        children += _visgroup_block(
            name, id_of[logical], indent="            ", color=color
        )
    text = _visgroup_block(
        "Railmancer",
        id_of[VISGROUP_RAILMANCER],
        children=children,
        indent="        ",
    )
    if include_original:
        text += _visgroup_block(
            "Original",
            id_of[VISGROUP_ORIGINAL],
            indent="        ",
            color="90 140 200",
        )
    return text


def _fresh_vis_ids():

    return {logical: logical for logical, _name, _parent, _color in _VISGROUP_SPECS}


def _clamp_index(value, count):
    if value < 0:
        return 0
    if value >= count:
        return count - 1
    return value


# (sector id, subsector ix, iy, grouping), or None if the prop stays loose.
# The sector id already separates stacked floors. Subsectors cut x/y.
def scatter_bucket(entity):
    if not _static_prop(entity):
        return None

    from railmancer import cfg, sectors

    grouping = entity.get("grouping")
    pos = entity.get("pos")
    if not grouping or not pos or len(pos) < 3:
        return None
    grouping = str(grouping)

    # Prefer the sector scatter recorded. Fall back to the position lookup.
    sector_id = entity.get("sector_id")
    sector = sectors.get(sector_id) if sector_id else None
    if not sector:
        sector_id = sectors.get_sector_id_at_position(pos)
        sector = sectors.get(sector_id) if sector_id else None
    if not sector:
        return None

    size = cfg.get("sector_real_size")
    n = int(cfg.get("prop_group_subdivisions"))
    if size <= 0:
        return None
    if n < 1:
        n = 1

    sub = size / n
    ix = _clamp_index(math.floor((pos[0] - sector["x"] * size) / sub), n)
    iy = _clamp_index(math.floor((pos[1] - sector["y"] * size) / sub), n)
    return (sector_id, ix, iy, grouping)


def _plan_new_ids():

    """Pick the object-id counter and the scatter-group id floor.

    Fresh files keep the old counters: objects from 1001, groups from
    GROUP_ID_BASE. An input file starts objects just above its max "id".
    Groups stay at GROUP_ID_BASE while that range is still above the
    input. If the input already used an id up there, groups take the ids
    immediately above that max and objects continue after the last group,
    so the two counters cannot meet.
    """

    global ID
    entities = get_entities()
    if base_map is None:
        group_ids = assign_scatter_groups(entities, GROUP_ID_BASE)
        sector_ids = _assign_sector_group_ids(GROUP_ID_BASE, len(group_ids))
        ID = 1000
        return group_ids, sector_ids

    if base_map.max_id + 1 >= GROUP_ID_BASE:
        group_base = base_map.max_id + 1
        group_ids = assign_scatter_groups(entities, group_base)
        sector_ids = _assign_sector_group_ids(group_base, len(group_ids))
        # Objects continue after the last group, scatter and sector alike.
        ID = base_map.max_id + len(group_ids) + len(sector_ids)
        return group_ids, sector_ids

    group_ids = assign_scatter_groups(entities, GROUP_ID_BASE)
    sector_ids = _assign_sector_group_ids(GROUP_ID_BASE, len(group_ids))
    ID = base_map.max_id
    return group_ids, sector_ids


def _assign_sector_group_ids(group_base, scatter_count):

    # One group per sector that actually emitted a brush. Rank is sorted
    # sector id, so the numbers do not depend on compile order. They start
    # after the scatter groups, which keep group_base + 0 .. count-1.
    global Sector_Group_IDs
    keys = sorted({key for key in Brush_Group_Keys if key is not None})
    Sector_Group_IDs = {}
    sector_ids = []
    for rank, key in enumerate(keys):
        group_id = str(group_base + scatter_count + rank)
        Sector_Group_IDs[key] = group_id
        sector_ids.append(group_id)
    return sector_ids


# One group per occupied (sector, cell x, cell y, grouping), including a lone prop.
# Id is the group floor plus the key's rank in sorted order, so it does not
# depend on prop order or on how many solids were written.
def assign_scatter_groups(entities, group_base=None):
    if group_base is None:
        group_base = GROUP_ID_BASE

    buckets = {}
    for entity in entities:
        if _static_prop(entity):
            entity.pop("groupid", None)
        key = scatter_bucket(entity)
        if key is None:
            continue
        buckets.setdefault(key, []).append(entity)

    group_ids = []
    for index, key in enumerate(sorted(buckets)):
        group_id = str(group_base + index)
        group_ids.append(group_id)
        for entity in buckets[key]:
            entity["groupid"] = group_id
    return group_ids


def format_prop_groups(group_ids):
    blocks = ""
    for group_id in group_ids:
        blocks += f"""
    group
    {{
        "id" "{group_id}"
        editor
        {{
            "color" "122 179 0"
            "visgroupshown" "1"
            "visgroupautoshown" "1"
        }}
    }}"""
    return blocks


# Assemble the brushes, entities, and brush-entity strings along with header information.
def _merge_spans(spans):

    # Union of the ranges, sorted and disjoint, so a point is covered by
    # at most one of them.
    if not spans:
        return ()
    ordered = sorted(spans)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            if end > prev_end:
                merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return tuple(merged)


def _covered(position, spans):

    # `spans` is the merged form from _merge_spans.
    if not spans:
        return False
    index = bisect.bisect_right(spans, (position, float("inf"))) - 1
    if index < 0:
        return False
    start, end = spans[index]
    return start <= position < end


def _editors_by_parent(blocks):

    # First editor child of each parent, which is what a linear scan found.
    editors = {}
    for block in blocks:
        if (
            block.name == "editor"
            and block.parent is not None
            and block.close_brace >= 0
            and block.parent not in editors
        ):
            editors[block.parent] = block
    return editors


def _block_span(text, block):

    from railmancer import vmfparse

    return vmfparse.line_start(text, block.start), block.close_brace + 1


def _deletion_spans(text, blocks, consumed_spans):

    """Spans to cut out of the input.

    Each consumed track entity is removed. A top-level hidden block whose
    entities are all consumed goes with them, so a rebuilt piece does not
    leave an empty hidden wrapper behind. A hidden block that still holds
    something else keeps the wrapper and loses only the track entity.
    """

    from railmancer import vmfparse

    consumed_entities = set()
    for index, block in enumerate(blocks):
        if block.name != "entity" or block.close_brace < 0:
            continue
        start, end = _block_span(text, block)
        if any(begin <= start and end <= stop for begin, stop in consumed_spans):
            consumed_entities.add(index)

    swallowed = set()
    deletions = []
    for index, block in enumerate(blocks):
        if block.name != "hidden" or block.parent is not None or block.close_brace < 0:
            continue
        entities = [
            child
            for child, child_block in enumerate(blocks)
            if child_block.name == "entity"
            and vmfparse.has_ancestor(blocks, child, {index})
        ]
        if entities and all(child in consumed_entities for child in entities):
            deletions.append(_block_span(text, block))
            swallowed.update(entities)

    for index in sorted(consumed_entities):
        if index in swallowed:
            continue
        deletions.append(_block_span(text, blocks[index]))
    return deletions


def _original_membership_inserts(text, blocks, deletions, original_id):

    """One extra visgroupid line on every preserved solid and entity.

    Hammer treats repeated visgroupid keys as membership in each group.
    The line is inserted on the editor's closing line, so the rest of
    that object stays as it was, including visgroupshown 0 and any
    hidden { } wrapper around it. An object with no editor gets a small
    one; otherwise it could not join Original.
    """

    from railmancer import vmfparse

    inserts = []
    needle = f'"visgroupid" "{original_id}"'
    editors = _editors_by_parent(blocks)
    covered = _merge_spans(deletions)
    for index, block in enumerate(blocks):
        if block.name not in ("solid", "entity") or block.close_brace < 0:
            continue
        if _covered(block.start, covered):
            continue

        editor = editors.get(index)
        if editor is not None:
            if _covered(editor.start, covered):
                continue
            body = text[editor.open_brace : editor.close_brace]
            if needle in body:
                continue
            # The key goes on its own line immediately above the editor's
            # closing brace, which stays exactly as it was.
            line_at = vmfparse.line_start(text, editor.close_brace)
            indent = text[line_at : editor.close_brace]
            extra = "\t" if "\t" in indent else "    "
            inserts.append((line_at, f'{indent}{extra}"visgroupid" "{original_id}"\n'))
            continue

        line_at = vmfparse.line_start(text, block.close_brace)
        indent = text[line_at : block.close_brace]
        inner = indent + ("\t" if "\t" in indent else "    ")
        inserts.append(
            (
                line_at,
                (
                    f"{indent}editor\n"
                    f"{indent}{{\n"
                    f'{inner}"visgroupid" "{original_id}"\n'
                    f'{inner}"visgroupshown" "1"\n'
                    f'{inner}"visgroupautoshown" "1"\n'
                    f"{indent}}}\n"
                ),
            )
        )
    return inserts


def _visgroup_insert(text, blocks, tree):

    from railmancer import vmfparse

    visgroups = [
        block
        for block in blocks
        if block.name == "visgroups" and block.parent is None and block.close_brace >= 0
    ]
    if visgroups:
        # In front of the visgroups block's closing line, so every group
        # that was already there is unchanged.
        at = vmfparse.line_start(text, visgroups[0].close_brace)
        return at, tree

    worlds = [
        block
        for block in blocks
        if block.name == "world" and block.parent is None and block.close_brace >= 0
    ]
    if not worlds:
        raise ValueError("The input VMF has no top-level world block.")
    at = vmfparse.line_start(text, worlds[0].start)
    return at, "visgroups\n{\n" + tree + "}\n"


def _line_after(text, position):

    # The first character of the line after the one that holds position.
    # Inserting on the closing line itself would land inside that block:
    # line_start of the character after "}" is still the "}" line, because
    # that character is the newline that ends it.
    newline = text.find("\n", position)
    if newline < 0:
        return len(text)
    return newline + 1


def _world_and_entity_insert_points(text, blocks):

    """Where new world contents and new entities are spliced.

    World contents go in front of the world's closing line, which is
    where this writer already puts solids and group blocks. Entities go
    on the line after the last top-level entity or hidden-entity block,
    which is in front of cameras and cordons and outside that block.
    """

    from railmancer import vmfparse

    worlds = [
        block
        for block in blocks
        if block.name == "world" and block.parent is None and block.close_brace >= 0
    ]
    if len(worlds) != 1:
        raise ValueError(
            f"Expected exactly one top-level world block, found {len(worlds)}."
        )
    world = worlds[0]
    entries = []
    for index, block in enumerate(blocks):
        if block.close_brace < 0:
            continue
        if block.name == "entity" and block.parent is None:
            entries.append(block)
            continue
        if block.name != "hidden" or block.parent is not None:
            continue
        contains_entity = any(
            child.name == "entity"
            and vmfparse.has_ancestor(blocks, child_index, {index})
            for child_index, child in enumerate(blocks)
        )
        if contains_entity:
            entries.append(block)

    if entries:
        last = max(entries, key=lambda block: block.close_brace)
        entity_at = _line_after(text, last.close_brace)
    else:
        entity_at = _line_after(text, world.close_brace)

    world_at = vmfparse.line_start(text, world.close_brace)
    return world_at, entity_at


def _apply_edits(text, deletions, insertions):

    # Drop an insert that would have landed inside a block we are deleting
    # (the editor of a consumed track entity). Edits are applied from the
    # end, so an earlier index still refers to the original string. The
    # pieces are collected and joined once instead of copying the whole
    # text for every edit. Equal positions keep the old order: deletions
    # were listed first, and the stable reverse sort leaves them ahead of
    # an insert at the same index, which means the insert is applied second
    # and therefore ends up in front of whatever the deletion left.
    covered = _merge_spans(deletions)
    insertions = [
        (pos, chunk)
        for pos, chunk in insertions
        if chunk and not _covered(pos, covered)
    ]
    operations = [("del", start, end, "") for start, end in deletions]
    operations.extend(("ins", pos, pos, chunk) for pos, chunk in insertions)
    operations.sort(key=lambda item: item[1], reverse=True)

    pieces = []
    cursor = len(text)
    for kind, start, end, chunk in operations:
        if end < cursor:
            pieces.append(text[end:cursor])
        if kind == "ins":
            pieces.append(chunk)
        cursor = start
    if cursor:
        pieces.append(text[:cursor])
    pieces.reverse()
    return "".join(pieces)


def _splice_base(brush_string, group_string, entity_string):

    from railmancer import vmfparse

    text = base_map.text
    blocks = vmfparse.parse_blocks(text)
    deletions = _deletion_spans(text, blocks, base_map.consumed_spans)
    insertions = _original_membership_inserts(
        text, blocks, deletions, base_map.vis_ids[VISGROUP_ORIGINAL]
    )
    insertions.append(
        _visgroup_insert(
            text,
            blocks,
            _format_visgroup_tree(base_map.vis_ids, include_original=True),
        )
    )

    world_at, entity_at = _world_and_entity_insert_points(text, blocks)
    world_chunk = brush_string + group_string
    if world_chunk and not world_chunk.endswith("\n"):
        world_chunk += "\n"
    if world_chunk:
        insertions.append((world_at, world_chunk))

    if entity_string and not entity_string.endswith("\n"):
        entity_string += "\n"
    if entity_string:
        insertions.append((entity_at, entity_string))

    return _apply_edits(text, deletions, insertions)


def assemble_vmf():

    with tools.stage("Allocating ids"):
        group_ids, sector_ids = _plan_new_ids()
    with tools.stage("Formatting"):
        BrushString = synthesize_brushes()
        GroupString = format_prop_groups(group_ids + sector_ids)
        EntityString = synthesize_entities(get_entities())
        BrushEntityString = synthesize_brush_entities()
        new_entities = EntityString + BrushEntityString

        if base_map is None:
            fresh = _fresh_vmf(BrushString, GroupString, new_entities)

    if base_map is not None:
        with tools.stage("Splicing"):
            return _splice_base(BrushString, GroupString, new_entities)
    return fresh


def _fresh_vmf(BrushString, GroupString, new_entities):

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
__VISGROUPS__    }
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

    Start = Start.replace(
        "__VISGROUPS__",
        _format_visgroup_tree(_fresh_vis_ids(), include_original=False),
    )

    return Start + BrushString + GroupString + "}" + new_entities + End


# Save the assembled VMF. Group blocks sit inside world, after the solids.
def write_to_vmf(filename):

    with tools.stage("Assembling the VMF"):
        content = assemble_vmf()

    directory = settings.get("vmf_output_dir")
    full_file_path = os.path.join(directory, filename)

    with tools.stage("Writing the file"):
        try:
            os.makedirs(directory, exist_ok=True)

            with open(full_file_path, "w", encoding="utf-8") as file:
                file.write(content)
            print(f"File saved successfully: {full_file_path}")
        except Exception as e:
            print(f"An error occurred: {e}")


# Convert a "raw" displacement + alpha and heights (presampled) into a properly compiled grid of data ready to be inserted into a displacement-brush string
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


# Places a frog entity at the supplied location (and rotation if requested)
def frog(pos, ang=[0, 0, 0]):

    add_entity(blank_entity(pos, "models/props_2fort/frog.mdl", ang))


# Visibility function for other systems to see all the current entities.
def get_entities():

    return Entities
