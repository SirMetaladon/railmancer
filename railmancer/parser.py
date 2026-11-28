from railmancer import track, lines, tools, vmfpy, vmfparse, cfg, switches
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

        switches.add_switch_stand(
            Pos, Entity["ang"][1], Data[0]["StartDirection"], lever_id
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

        # import_track already parsed the path. Calling process_file again
        # would write the straight cache a second time for the same model.
        Data = raw_ent.get("data")
        if Data is None:
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


_TRACK_FIELD = re.compile(
    r'"model"\s*"([^"]+)"|'
    r'"origin"\s*"([^"]+)"|'
    r'"angles"\s*"([^"]+)"|'
    r'"skin"\s*"([^"]+)"|'
    r'"classname"\s*"([^"]+)"|'
    r'"lever"\s*"([^"]+)"'
)


def _fields_in_block(block_text):

    matches = _TRACK_FIELD.findall(block_text)

    def first(index):
        return next((row[index] for row in matches if row[index]), None)

    return {
        "model": first(0),
        "origin": first(1),
        "angles": first(2),
        "skin": first(3),
        "classname": first(4),
        "lever": first(5),
    }


def track_entities_to_rebuild(text):
    """Trakpak entities this import will replace with rebuilt copies.

    The block parser supplies the entity, because a regex stops at the
    first closing brace and cannot name the span to delete later. The
    decision is the old one: a model path containing trakpak3_rsg, plus
    origin and angles, and process_file actually returns routes. A model
    it refuses (bumpers, unknown families) stays in the file. So does a
    prop in the Build Sheds visgroup: it is not mainline, and it is not
    a line, so it does not grow a sector.
    """

    blocks = vmfparse.parse_blocks(text)
    # Shed track lives in the "Build Sheds" visgroup. The id is whatever
    # Hammer or resolve_visgroup wrote, so the name is the test, not "31".
    shed_ids = vmfparse.visgroup_ids_named(text, vmfpy.BUILD_SHEDS_VISGROUP_NAME)
    found = []
    for block in blocks:
        if block.name != "entity" or block.close_brace < 0:
            continue
        block_text = text[block.start : block.close_brace + 1]
        if shed_ids and vmfparse.block_visgroup_ids(block_text) & shed_ids:
            continue
        fields = _fields_in_block(block_text)
        model = fields["model"]
        if not (
            model and fields["origin"] and fields["angles"] and "trakpak3_rsg" in model
        ):
            continue
        data = track.process_file(model)
        if not data:
            continue
        start = vmfparse.line_start(text, block.start)
        fields["data"] = data
        fields["span"] = (start, block.close_brace + 1)
        fields["raw"] = block_text
        found.append(fields)
    return found


def import_track(path):

    if path == "":
        # No input file: the next write is a fresh VMF, same as before.
        vmfpy.clear_base_map()
        return [], []

    # newline="" keeps the input's own line endings for the passthrough.
    with open(path, "r", encoding="utf-8", newline="") as file:
        content = file.read()

    sections = vmfparse.split_vmf_text(content)

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
                verts2, cfg.get("line_maximum_poll_point_distance") * 2
            )

            lines.stage_points(verts2 + verts3)

    raw_ents = track_entities_to_rebuild(content)
    # The writer keeps this text and cuts these spans so the rebuilt
    # props are not added on top of the originals.
    vmfpy.set_base_map(content, [ent["span"] for ent in raw_ents])

    print(f"Imported {path}, {len(raw_ents)} entities.")
    tools.stopwatch_click("submodule", "Import complete")

    reprocess_raw_data(raw_ents)
