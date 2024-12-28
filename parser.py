"""
#blockout:

import a vmf as a string

break it up into sections for preamble, solids, entities, etc

for the entities section, break it by sub-part and identify models of interest




"""


def reprocess_raw_data(raw_entities):

    import track

    Entities = []
    Line = []

    # recompile
    for raw_ent in raw_entities:

        Pos = raw_ent["origin"].split(" ")
        Ang = raw_ent["angles"].split(" ")

        Entities += [
            {
                "pos-x": float(Pos[0]),
                "pos-y": float(Pos[1]),
                "pos-z": float(Pos[2]),
                "mdl": raw_ent["model"],
                "skin": raw_ent["skin"],
                "ang-yaw": float(Ang[1]),
            }
        ]

        Data = track.process_file(raw_ent["model"])

        print(Data)

    return Entities, Line


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


import_track("scan/start.vmf")
