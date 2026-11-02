"""Endpoint census for placed track props.

Every joint in a finished run is one piece's end meeting the next piece's
start, so each endpoint vector appears exactly twice. A count of 1 is a gap
(or a legitimate open end). Three or more means more than two rails meet,
which is invalid. Open ends have to sit on the plain multi-track spacing
from move_in_trackspace.
"""

import math

from railmancer import tools, track


def _unit_xy(vector):
    length = math.hypot(float(vector[0]), float(vector[1]))
    if length == 0:
        return (0.0, 0.0)
    return (float(vector[0]) / length, float(vector[1]) / length)


def canonical_tangent(vector):
    """Undirected rail heading. Opposite tangents are the same joint."""

    x, y = _unit_xy(vector)
    if x < -1e-9 or (abs(x) <= 1e-9 and y < 0):
        x, y = -x, -y
    return (round(x, 4), round(y, 4))


def position_key(point):
    return tuple(int(round(float(component))) for component in list(point)[:3])


def endpoint_key(point, tangent):
    return (position_key(point), canonical_tangent(tangent))


def prop_endpoints(model_name, origin, yaw, library):
    """Both ends of one prop, from its model, origin, and yaw."""

    data = library[model_name]
    yaw = float(yaw)
    end = [
        float(origin[i]) + float(tools.rot_orth(data["Move"], yaw)[i]) for i in range(3)
    ]
    start_tangent = tools.rot_orth(track.get_heading(data["StartDirection"]), yaw)
    end_tangent = tools.rot_orth(track.get_heading(data["EndDirection"]), yaw)
    return (
        endpoint_key(origin, start_tangent),
        endpoint_key(end, end_tangent),
    )


def tally_endpoints(props, library):
    """Map endpoint key -> how many prop-ends land on it.

    `props` entries need mdl, pos (3 numbers), and ang (pitch, yaw, roll)
    or a bare yaw number.
    """

    counts = {}
    where = {}
    for index, prop in enumerate(props):
        yaw = prop["ang"][1] if not isinstance(prop["ang"], (int, float)) else prop["ang"]
        ends = prop_endpoints(prop["mdl"], prop["pos"], yaw, library)
        for which, key in enumerate(ends):
            counts[key] = counts.get(key, 0) + 1
            where.setdefault(key, []).append((index, which))
    return counts, where


def _right_step(tangent):
    """World sideways step of one track, using move_in_trackspace.

    Match the observed tangent to a known direction at a 90° heading, then
    return that direction's one-track right vector in world space.
    """

    observed = _unit_xy(tangent)
    best = None
    best_dot = -2
    best_right = None
    for direction in (
        "0fw",
        "1lt",
        "1rt",
        "2lt",
        "2rt",
        "4lt",
        "4rt",
        "8lt",
        "8rt",
    ):
        forward = track.get_heading(direction)
        right = track.move_in_trackspace(0, direction, 1)
        for heading in (0, 90, 180, 270):
            turned = _unit_xy(tools.rot_orth(forward, heading))
            score = abs(turned[0] * observed[0] + turned[1] * observed[1])
            if score > best_dot:
                best_dot = score
                world_right = tools.rot_orth(right, heading)
                best_right = (float(world_right[0]), float(world_right[1]), float(world_right[2]))
                best = direction
    if best_dot < 0.99:
        return None
    return best_right


def open_ends_follow_spacing(open_keys):
    """True when every count-1 row is spaced by one move_in_trackspace step.

    A lone open end is a one-track run end and has no neighbor to check.
    """

    problems = []
    groups = {}
    for key in open_keys:
        position, tangent = key
        groups.setdefault(tangent, []).append(position)

    for tangent, positions in groups.items():
        if len(positions) < 2:
            continue
        right = _right_step(tangent)
        if right is None:
            problems.append(f"open ends with heading {tangent} do not match a track direction")
            continue
        lateral = (right[0], right[1])
        length = math.hypot(lateral[0], lateral[1])
        if length < 1:
            problems.append(f"open ends with heading {tangent} have no sideways step")
            continue
        axis = (lateral[0] / length, lateral[1] / length)
        # The start of a run and the end of a run share a heading but sit far
        # apart along the rails. Check spacing only inside one cross-section.
        along = (-axis[1], axis[0])
        rows = {}
        for point in positions:
            station = int(round(point[0] * along[0] + point[1] * along[1]))
            rows.setdefault(station, []).append(point)
        for row in rows.values():
            ordered = sorted(row, key=lambda point: point[0] * axis[0] + point[1] * axis[1])
            for left, right_point in zip(ordered, ordered[1:]):
                delta = (
                    right_point[0] - left[0],
                    right_point[1] - left[1],
                    right_point[2] - left[2],
                )
                steps = (delta[0] * axis[0] + delta[1] * axis[1]) / length
                nearest = max(1, int(round(steps)))
                expect = (lateral[0] * nearest, lateral[1] * nearest, 0.0)
                error = max(abs(delta[i] - expect[i]) for i in range(3))
                if error > 0.5:
                    problems.append(
                        f"open ends {left} and {right_point} are {error:.1f} off "
                        f"move_in_trackspace spacing {tuple(int(round(v)) for v in expect)}"
                    )
    return problems


def describe_endpoint(key, count):
    position, tangent = key
    kind = "meets" if count == 2 else ("gap or open end" if count == 1 else "invalid junction")
    return f"count {count} ({kind}) at {position} heading {tangent}"


def audit_props(props, library, allowed_open=None):
    """Return problem strings. Empty means every joint is exactly two ends.

    `allowed_open` is a set of endpoint keys that may appear once: the start
    and end of each run, already on move_in_trackspace spacing.
    """

    counts, _where = tally_endpoints(props, library)
    problems = []
    open_keys = [key for key, count in counts.items() if count == 1]
    allowed = set(allowed_open) if allowed_open is not None else None

    for key, count in sorted(counts.items(), key=lambda item: (item[0][0], item[0][1])):
        if count == 2:
            continue
        if count == 1 and allowed is not None and key in allowed:
            continue
        if count == 1 and allowed is None:
            continue
        problems.append(describe_endpoint(key, count))

    if allowed is not None:
        for key in sorted(allowed, key=lambda item: (item[0], item[1])):
            count = counts.get(key, 0)
            if count == 0:
                problems.append(f"missing run end {describe_endpoint(key, 0)}")
            elif count != 1:
                problems.append(
                    f"run end was not a single open endpoint: {describe_endpoint(key, count)}"
                )
    else:
        problems.extend(open_ends_follow_spacing(open_keys))

    return problems


def parse_vmf_track_props(vmf_text):
    """prop_static / prop_dynamic track pieces named in a VMF."""

    props = []
    index = 0
    while True:
        start = vmf_text.find("entity", index)
        if start < 0:
            break
        brace = vmf_text.find("{", start)
        if brace < 0:
            break
        depth = 0
        cursor = brace
        end = None
        while cursor < len(vmf_text):
            character = vmf_text[cursor]
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    end = cursor
                    break
            cursor += 1
        if end is None:
            break
        block = vmf_text[brace : end + 1]
        index = end + 1
        prop = _prop_from_entity_block(block)
        if prop is not None:
            props.append(prop)
    return props


def _quoted(block, field):
    needle = f'"{field}"'
    at = block.find(needle)
    if at < 0:
        return None
    first = block.find('"', at + len(needle))
    second = block.find('"', first + 1)
    if first < 0 or second < 0:
        return None
    return block[first + 1 : second]


def _prop_from_entity_block(block):
    model = _quoted(block, "model")
    if not model or "trakpak" not in model.replace("\\", "/").lower():
        return None
    lowered = model.replace("\\", "/").lower()
    if "/arcs/" not in lowered and "/straights/" not in lowered and "/banked/" not in lowered:
        return None
    origin = _quoted(block, "origin")
    angles = _quoted(block, "angles")
    if origin is None or angles is None:
        return None
    origin_values = [float(part) for part in origin.split()]
    angle_values = [float(part) for part in angles.split()]
    return {"mdl": model.replace("\\", "/"), "pos": origin_values, "ang": angle_values}


def library_from_prop_names(props):
    """Piece geometry is encoded in the TrackPack 3 model name."""

    library = {}
    unknown = []
    for prop in props:
        model = prop["mdl"]
        if model in library:
            continue
        try:
            parsed = track.process_file(model)
        except (IndexError, ValueError, ZeroDivisionError):
            parsed = []
        if not parsed:
            unknown.append(model)
            continue
        library[model] = parsed[0]
    return library, unknown
