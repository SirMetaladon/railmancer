from railmancer import track, lines, tools, vmfpy, vmfparse, cfg
import numpy as np
import re
import itertools
import math

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

        Pos = tuple(map(float, raw_ent["origin"].split()))
        Ang = tuple(map(float, raw_ent["angles"].split()))

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


def extract_vertices(text):

    pattern = r'"v"\s+"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"'

    vertices = {tuple(map(float, match)) for match in re.findall(pattern, text)}

    return list(vertices)


import math


import math


def fill_convex_polygon_3d(vertices, spacing):
    """Generates a grid of 3D points filling the area of a convex polygon.

    :param vertices: List of (x, y, z) tuples representing the unordered polygon
    vertices.
    :param spacing: Distance between grid points.
    :return: List of (x, y, z) tuples covering the polygon area.
    """
    if not vertices or spacing <= 0:
        return []

    # 1. Extract the common z height
    z = vertices[0][2]

    # 2. Order the unordered vertices by their polar angle around the centroid
    cx = sum(v[0] for v in vertices) / len(vertices)
    cy = sum(v[1] for v in vertices) / len(vertices)
    ordered = sorted(vertices, key=lambda v: math.atan2(v[1] - cy, v[0] - cx))

    # 3. Find the 2D bounding box
    xs = [v[0] for v in ordered]
    ys = [v[1] for v in ordered]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # 4. Helper: Check if a 2D point is inside/on a convex polygon using cross products
    def is_inside(px, py):
        n = len(ordered)
        sign = None
        for i in range(n):
            v1 = ordered[i]
            v2 = ordered[(i + 1) % n]

            # Edge vector and point vector
            dx = v2[0] - v1[0]
            dy = v2[1] - v1[1]
            pdx = px - v1[0]
            pdy = py - v1[1]

            # 2D cross product
            cross = dx * pdy - dy * pdx

            # Skip points exactly on collinear edges (within floating-point tolerance)
            if abs(cross) < 1e-9:
                continue

            current_sign = cross > 0
            if sign is None:
                sign = current_sign
            elif sign != current_sign:
                return False
        return True

    # 5. Generate grid points and filter
    filled_points = []
    y = min_y
    while y <= max_y:
        x = min_x
        while x <= max_x:
            if is_inside(x, y):
                filled_points.append((x, y, z))
            x += spacing
        y += spacing

    return filled_points


def import_track(path):

    if path == "":
        return [], []

    sections = vmfparse.split_vmf(path)

    imported_brushes = sections.Brushes

    pattern = r'"name"\s+"groundhints"\s*\n\s*"visgroupid"\s*"(\d+)"'
    match = re.search(pattern, sections.Start)

    if match:
        visgroupnumber = match.group(1)
    else:
        visgroupnumber = "0"

    for brush in imported_brushes:

        if '''"visgroupid" "''' + visgroupnumber + '''"''' in brush:

            vertices = extract_vertices(brush)
            verts2 = []
            verts3 = []

            if not vertices:
                print(brush)

            vertices = [(x, y, z + 35) for x, y, z in vertices]
            min_z = min(z for _, _, z in vertices)

            verts2 = [(x, y, z) for x, y, z in vertices if z == min_z]

            verts3 = fill_convex_polygon_3d(
                verts2, cfg.get("line_maximum_poll_point_distance")
            )
            """
            pairs = list(itertools.combinations(verts2, 2))

            maxlength = 400

            for pair in pairs:
                v1, v2 = pair
                p1 = np.array(v1)
                p2 = np.array(v2)

                dist = np.linalg.norm(p1 - p2)

                if dist < maxlength:
                    continue
                count = math.ceil(dist / maxlength)
                spots = tools.split_into_parts(1, count)

                for spot in spots:
                    verts3 += [tools.linterp(p1, p2, spot)]"""

            lines.stage_points(verts2 + verts3)

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
