from railmancer import track, lines, tools, vmfpy
import numpy as np

# Subsystem for taking raw VMFs and converting them into usable dictionaries of data.

lever_id_incrementor = 0


def get_lever():

    global lever_id_incrementor
    lever_id_incrementor += 1
    return f"switch_{lever_id_incrementor}"


def add_entity_to_new_map(Entity, Data):

    Pos = Entity["pos"]

    # Regardless of what type it is, add lines for it if it's got data
    for trackdata_chunk in Data:

        track.add_lines_from_track(Pos, trackdata_chunk, Entity["ang"][1])

    if not "switches" in Entity["mdl"]:

        vmfpy.add_entity(Entity)

    else:

        lever_id = get_lever()
        Entity["lever"] = lever_id
        Entity["classname"] = "tp3_switch"

        vmfpy.add_entity(Entity)

        StandAngle = Entity["ang"][1] + track.direction_to_angle(
            Data[0]["StartDirection"]
        )

        StandPos1 = np.add(
            Pos,
            tools.rot3(np.array([-110, -100, -17.5]), StandAngle),
        )

        StandPos2 = np.add(Pos, tools.rot3(np.array([-110, 100, -17.5]), StandAngle))

        GravelPos1 = np.add(Pos, tools.rot3(np.array([-110, 0, 0]), StandAngle))
        GravelPos2 = np.add(Pos, tools.rot3(np.array([-110, 0, 0]), StandAngle))
        # models/trakpak3_us/switchstands/bethlehem_51a_right.mdl
        # models/trakpak3_us/switchstands/racor_112e_right.mdl
        # models/trakpak3_common/ballast/ballast_pile_switch.mdl

        vmfpy.add_entity(
            [
                ["collapse", StandPos1, StandPos2],
                {
                    "pos": StandPos1,
                    "mdl": "models/trakpak3_us/switchstands/bethlehem_51a_right.mdl",
                    "ang": (0, StandAngle, 0),
                    "lever": lever_id,
                    "classname": "tp3_switch_lever_anim",
                    "visgroup": "23",
                },
                {
                    "pos": StandPos2,
                    "mdl": "models/trakpak3_us/switchstands/bethlehem_51a_right.mdl",
                    "ang": (0, 180 + StandAngle, 0),
                    "lever": lever_id,
                    "classname": "tp3_switch_lever_anim",
                    "visgroup": "23",
                },
            ]
        )

        vmfpy.add_entity(
            [
                ["collapse", StandPos1, StandPos2],
                {
                    "pos": GravelPos1,
                    "mdl": "models/trakpak3_common/ballast/ballast_pile_switch.mdl",
                    "ang": (0, 180 + StandAngle, 0),
                    "classname": "prop_static",
                    "visgroup": "23",
                },
                {
                    "pos": GravelPos2,
                    "mdl": "models/trakpak3_common/ballast/ballast_pile_switch.mdl",
                    "ang": (0, StandAngle, 0),
                    "classname": "prop_static",
                    "visgroup": "23",
                },
            ]
        )


def reprocess_raw_data(raw_ents):

    # recompile
    for raw_ent in raw_ents:

        Pos = (float(coord) for coord in raw_ent["origin"].split(" "))
        Ang = (float(coord) for coord in raw_ent["angles"].split(" "))

        # if raw_ent["classname"] != "prop_static":
        # Entities += [{"raw_entity": raw_ent["raw"] + "}"}]

        Entity = {
            "pos": Pos,
            "mdl": raw_ent["model"],
            "skin": raw_ent["skin"],
            "ang": Ang,
            "visgroup": "25",
        }

        Data = track.process_file(Entity["mdl"])

        if Data:

            add_entity_to_new_map(Entity, Data)


def import_track(path):

    if path == "":
        return [], []

    import re

    with open(path, "r") as file:
        content = file.read()

    entity_pattern = re.compile(r"entity\s*{(.*?)}", re.DOTALL)
    subdata_pattern = re.compile(
        r'"model"\s*"([^"]+)"|'
        r'"origin"\s*"([^"]+)"|'
        r'"angles"\s*"([^"]+)"|'
        r'"skin"\s*"([^"]+)"|'
        r'"classname"\s*"([^"]+)"|'
        r'"lever"\s*"([^"]+)"'
    )

    raw_ents = []
    for match in entity_pattern.finditer(content):
        entity_block = match.group(0)
        model_origin_matches = subdata_pattern.findall(entity_block)
        model = next((m for m, _, _, _, _, _ in model_origin_matches if m), None)
        origin = next((o for _, o, _, _, _, _ in model_origin_matches if o), None)
        angles = next((a for _, _, a, _, _, _ in model_origin_matches if a), None)
        skin = next((s for _, _, _, s, _, _ in model_origin_matches if s), None)
        classname = next((c for _, _, _, _, c, _ in model_origin_matches if c), None)
        lever = next((l for _, _, _, _, _, l in model_origin_matches if l), None)

        if model and origin and angles and "trakpak3_rsg" in model:
            raw_ents.append(
                {
                    "model": model,
                    "origin": origin,
                    "angles": angles,
                    "skin": skin,
                    "classname": classname,
                    "lever": lever,
                    "raw": entity_block,
                }
            )

    print(f"Imported {path}, {len(raw_ents)} entities.")
    tools.stopwatch_click("submodule", "Import complete")

    reprocess_raw_data(raw_ents)
