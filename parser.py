import track, lines, tools, entities
import numpy as np


def get_lever():
    global Lever

    Lever += 1
    return f"switch_{Lever}"


def reprocess_raw_data(raw_entities):

    Beziers = []

    # recompile
    for raw_ent in raw_entities:

        Pos = [float(coord) for coord in raw_ent["origin"].split(" ")]
        Ang = [float(coord) for coord in raw_ent["angles"].split(" ")]

        # if raw_ent["classname"] != "prop_static":
        # Entities += [{"raw_entity": raw_ent["raw"] + "}"}]

        Entity = {
            "pos-x": Pos[0],
            "pos-y": Pos[1],
            "pos-z": Pos[2],
            "mdl": raw_ent["model"],
            "skin": raw_ent["skin"],
            "ang-pitch": Ang[0],
            "ang-yaw": Ang[1],
            "ang-roll": Ang[2],
        }

        Data = track.process_file(raw_ent["model"])

        if Data:

            if "switches" in raw_ent["model"]:

                Lever = get_lever()
                Entity["lever"] = Lever
                Entity["classname"] = "tp3_switch"

                entities.add(Entity)

                StandAngle = Ang[1] + track.direction_to_angle(
                    Data[0]["StartDirection"]
                )

                StandPos1 = np.add(
                    Pos,
                    tools.rot_z(np.array([-110, -75, -17.5]), StandAngle),
                )

                StandPos2 = np.add(
                    Pos, tools.rot_z(np.array([-110, 75, -17.5]), StandAngle)
                )

                entities.add(
                    [
                        ["collapse", StandPos1, StandPos2],
                        {
                            "pos-x": StandPos1[0],
                            "pos-y": StandPos1[1],
                            "pos-z": StandPos1[2],
                            "mdl": "models/trakpak3_us/switchstands/racor_112e_right.mdl",
                            "ang-yaw": StandAngle,
                            "lever": Lever,
                            "classname": "tp3_switch_lever_anim",
                        },
                        {
                            "pos-x": StandPos2[0],
                            "pos-y": StandPos2[1],
                            "pos-z": StandPos2[2],
                            "mdl": "models/trakpak3_us/switchstands/racor_112e_right.mdl",
                            "ang-yaw": 180 + StandAngle,
                            "lever": Lever,
                            "classname": "tp3_switch_lever_anim",
                        },
                    ]
                )

            else:

                entities.add(Entity)

            for Subsection in Data:  # this is a rail that needs a line

                EndPos = Pos + tools.rot_z(Subsection["Move"], Ang[1])

                Beziers += [
                    lines.bezier_curve_points(
                        Pos,
                        EndPos,
                        tools.rot_z(
                            track.get_heading(Subsection["StartDirection"]), Ang[1]
                        ),
                        tools.rot_z(
                            track.get_heading(Subsection["EndDirection"]), Ang[1] + 180
                        ),
                    )
                ]

    return Beziers


def import_track(path):

    if path == "":
        return [], []

    import re

    global Lever

    # initialize
    Lever = 0

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

    entities = []
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
            entities.append(
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

    print("Imported " + path)

    return reprocess_raw_data(entities)
