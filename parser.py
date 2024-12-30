"""
#blockout:

import a vmf as a string

break it up into sections for preamble, solids, entities, etc

for the entities section, break it by sub-part and identify models of interest




"""


def reprocess_raw_data(raw_entities):

    import track, curvature, tools

    Entities = []
    Beziers = []

    # recompile
    for raw_ent in raw_entities:

        Pos = [float(coord) for coord in raw_ent["origin"].split(" ")]
        Ang = [float(coord) for coord in raw_ent["angles"].split(" ")]

        Entities += [
            {
                "pos-x": Pos[0],
                "pos-y": Pos[1],
                "pos-z": Pos[2],
                "mdl": raw_ent["model"],
                "skin": raw_ent["skin"],
                "ang-yaw": Ang[1],
            }
        ]

        Data = track.process_file(raw_ent["model"])

        # start point is always just the 0 of the model
        if Data:  # this is a rail that needs a line

            EndPos = Pos + tools.rot_z(Data["Move"], Ang[1])

            Beziers += [
                curvature.bezier_curve_points(
                    Pos,
                    EndPos,
                    tools.rot_z(track.get_heading(Data["StartDirection"]), Ang[1]),
                    tools.rot_z(track.get_heading(Data["EndDirection"]), Ang[1] + 180),
                )
            ]

    return Beziers, Entities


def import_track(path):

    import re

    with open(path, "r") as file:
        content = file.read()

    entity_pattern = re.compile(r"entity\s*{(.*?)}", re.DOTALL)
    subdata_pattern = re.compile(
        r'"model"\s*"([^"]+)"|'
        r'"origin"\s*"([^"]+)"|'
        r'"angles"\s*"([^"]+)"|'
        r'"skin"\s*"([^"]+)"'
    )

    entities = []
    for match in entity_pattern.finditer(content):
        entity_block = match.group(0)
        model_origin_matches = subdata_pattern.findall(entity_block)
        model = next((m for m, o, a, s in model_origin_matches if m), None)
        origin = next((o for m, o, a, s in model_origin_matches if o), None)
        angles = next((a for m, o, a, s in model_origin_matches if a), None)
        skin = next((s for m, o, a, s in model_origin_matches if s), None)
        if model and origin and angles and "trakpak3_rsg" in model:
            entities.append(
                {"model": model, "origin": origin, "angles": angles, "skin": skin}
            )

    return reprocess_raw_data(entities)
