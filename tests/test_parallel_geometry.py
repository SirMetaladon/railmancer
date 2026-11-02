"""Headless geometry check for parallel mainline track.

Hammer models are not required. Backbone pieces are synthetic arcs with the
same direction vectors and Move convention as Trakpak3, and straight fillers
are built from the filenames ``convert_length_to_mdl`` already emits.

What is checked, for every grid-legal direction change, both ways through the
piece, at headings 0/90/180/270, and for every track count from 0 to 3 on
each side:

* consecutive pieces meet in position
* the centerline heading is continuous across each joint
* at every backbone node, track ``t`` sits on the lateral offset of ``t``
  tracks to the right of main (192 units when the node direction is ``0fw``)
"""

import contextlib
import io
import math
import os
import random
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# lines.py imports turtle, which imports tkinter. Geometry tests never draw.
sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import lines, track, tools, vmfpy
from railmancer.joincheck import audit_props, endpoint_key

NODE_DIRS = ("0fw", "1lt", "1rt", "2lt", "2rt", "4lt", "4rt")
ALL_DIRS = NODE_DIRS + ("8lt", "8rt")
OTHER_4 = {"4lt": "4rt", "4rt": "4lt"}
HEADINGS = (0, 90, 180, 270)
MODES = tuple((left, right) for left in range(4) for right in range(4))
TANGENT_DOT = 0.999
# The hand-tuned table, travel order, one track to the right.
# Kept so a solver change cannot silently drift off the values that already
# matched these curves.
LEGACY_OFFSETS = {
    ("0fw", "1rt"): (-48, 0),
    ("0fw", "1lt"): (48, 0),
    ("0fw", "2rt"): (-96, 0),
    ("0fw", "2lt"): (96, 0),
    ("0fw", "4rt"): (-96, -48),
    ("0fw", "4lt"): (96, 48),
    ("0fw", "8rt"): (-192, -192),
    ("0fw", "8lt"): (192, 192),
    ("1rt", "2rt"): (-96, 48),
    ("1lt", "2lt"): (96, -48),
    ("1rt", "4rt"): (-64, -32),
    ("1lt", "4lt"): (64, 32),
    ("2rt", "4rt"): (0, -48),
    ("2lt", "4lt"): (0, 48),
}


class StraightLib(dict):
    """Resolve filler straights from the filename the same way the mdl parser does."""

    def __getitem__(self, key):
        if key not in self and "straights" in str(key):
            parsed = track.process_file(key)
            if not parsed:
                raise KeyError(key)
            self[key] = parsed[0]
        return dict.__getitem__(self, key)


def _unit_xy(vector):
    length = math.hypot(float(vector[0]), float(vector[1]))
    if length == 0:
        return (0.0, 0.0)
    return (float(vector[0]) / length, float(vector[1]) / length)


def _point_key(point):
    return tuple(int(round(float(component))) for component in point[:3])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def grid_offset(start_direction, end_direction):
    """Independent copy of the stagger equation, used to classify transitions."""

    if start_direction == end_direction:
        return 0, 0, True
    fwd_s = track.move_in_trackspace(1, start_direction, 0)
    right_s = track.move_in_trackspace(0, start_direction, 1)
    fwd_e = track.move_in_trackspace(1, end_direction, 0)
    right_e = track.move_in_trackspace(0, end_direction, 1)
    rhs_x = right_e[0] - right_s[0]
    rhs_y = right_e[1] - right_s[1]
    det = fwd_s[0] * fwd_e[1] - fwd_s[1] * fwd_e[0]
    if abs(det) < 1e-8:
        return None, None, False
    along_start = (rhs_x * fwd_e[1] - rhs_y * fwd_e[0]) / det
    along_end = (fwd_s[0] * rhs_y - fwd_s[1] * rhs_x) / det
    if abs(along_start - round(along_start)) > 1e-4:
        return along_start, along_end, False
    if abs(along_end - round(along_end)) > 1e-4:
        return along_start, along_end, False
    along_start = int(round(along_start))
    along_end = int(round(along_end))
    if along_start % 16 != 0 or along_end % 16 != 0:
        return along_start, along_end, False
    return along_start, along_end, True


def backbone_move(start_direction, end_direction):
    start = track.move_in_trackspace(1536, start_direction)
    end = track.move_in_trackspace(1536, end_direction)
    return (
        int(round(start[0] + end[0])),
        int(round(start[1] + end[1])),
        48,
    )


def register_library():
    library = StraightLib()
    models = {}
    for start_direction in ALL_DIRS:
        for end_direction in ALL_DIRS:
            name = (
                "models/trakpak3_rsg/arcs/r4096/"
                f"a{start_direction}_{end_direction}_geom.mdl"
            )
            library[name] = {
                "Length": 3000,
                "Radius": 0 if start_direction == end_direction else 4096,
                "StartDirection": start_direction,
                "EndDirection": end_direction,
                "GradeLevel": 0,
                "Move": backbone_move(start_direction, end_direction),
                "ApproxGrade": 0,
                "RealGrade": 0,
            }
            models[(start_direction, end_direction)] = name
    track.track_model_library = library
    return models


def advance(node, model, mode):
    prev_direction = node[1]
    end_direction = track.get_end_direction(model, prev_direction)
    current_direction = track.get_end_direction(model, end_direction)
    add_start, add_end = track.get_addlength(current_direction, end_direction, mode)
    return track.get_new_node_from_node_and_model(
        model, node, False, add_start, add_end
    )


def make_node(direction, heading, position=(0, 0, 32)):
    return (position, direction, heading, False)


def station_point(node, track_index):
    return track.updated_position(
        node[0], track.move_in_trackspace(0, node[1], track_index), node[2]
    )


def node_tangent(node):
    return _unit_xy(tools.rot_orth(track.get_heading(node[1]), node[2]))


def lateral_step(node):
    origin = station_point(node, 0)
    right = station_point(node, 1)
    return (
        float(right[0] - origin[0]),
        float(right[1] - origin[1]),
        float(right[2] - origin[2]),
    )


class Segment:
    def __init__(self, start, end, tangent_start, tangent_end):
        self.point = (start, end)
        self.tangent = (tangent_start, tangent_end)

    def walk(self, from_end):
        if from_end == 0:
            return self.tangent[0], self.tangent[1], 1
        return (
            (-self.tangent[1][0], -self.tangent[1][1]),
            (-self.tangent[0][0], -self.tangent[0][1]),
            0,
        )


def collect_segments(entities):
    segments = []
    adjacency = {}
    for entity in entities:
        data = track.track_model_library[entity["mdl"]]
        yaw = entity["ang"][1]
        start = entity["pos"]
        end = start + tools.rot_orth(data["Move"], yaw)
        tangent_start = _unit_xy(
            tools.rot_orth(track.get_heading(data["StartDirection"]), yaw)
        )
        tangent_end = _unit_xy(
            tools.rot_orth(track.get_heading(data["EndDirection"]), yaw)
        )
        segment = Segment(start, end, tangent_start, tangent_end)
        index = len(segments)
        segments.append(segment)
        for end_id, point in ((0, start), (1, end)):
            adjacency.setdefault(_point_key(point), []).append((index, end_id))
    return segments, adjacency


def _best_departure(adjacency, segments, key, used, target_tangent):
    best = None
    best_dot = -2
    for index, end_id in adjacency.get(key, []):
        if index in used:
            continue
        depart, _arrive, _other = segments[index].walk(end_id)
        score = _dot(depart, target_tangent)
        if score > best_dot:
            best_dot = score
            best = (index, end_id, depart)
    return best, best_dot


def walk_track(name, adjacency, segments, used, nodes, track_index):
    failures = []
    start_key = _point_key(station_point(nodes[0], track_index))
    end_key = _point_key(station_point(nodes[-1], track_index))
    if start_key not in adjacency:
        failures.append(f"{name} track {track_index}: start station missing {start_key}")
        return failures
    tangent = node_tangent(nodes[0])
    chosen, score = _best_departure(adjacency, segments, start_key, used, tangent)
    if chosen is None or score < TANGENT_DOT:
        failures.append(
            f"{name} track {track_index}: start heading dot {score:.4f} at {start_key}"
        )
        return failures

    path = [start_key]
    travel_tangent = {start_key: tangent}
    current = start_key
    guard = 0
    while current != end_key:
        guard += 1
        if guard > len(segments) + 2:
            failures.append(f"{name} track {track_index}: chain did not reach the end")
            return failures
        index, end_id, _depart = chosen
        used.add(index)
        depart, arrive, other_end = segments[index].walk(end_id)
        if _dot(depart, travel_tangent[current]) < TANGENT_DOT:
            failures.append(
                f"{name} track {track_index}: left {current} with heading dot "
                f"{_dot(depart, travel_tangent[current]):.4f}"
            )
            return failures
        nxt = _point_key(segments[index].point[other_end])
        path.append(nxt)
        travel_tangent[nxt] = arrive
        current = nxt
        if nxt == end_key:
            if _dot(arrive, node_tangent(nodes[-1])) < TANGENT_DOT:
                failures.append(
                    f"{name} track {track_index}: end heading dot "
                    f"{_dot(arrive, node_tangent(nodes[-1])):.4f}"
                )
            break
        # Joint with the following piece: headings have to agree.
        nxt_choice, nxt_score = _best_departure(
            adjacency, segments, nxt, used, arrive
        )
        if nxt_choice is None or nxt_score < TANGENT_DOT:
            if nxt_choice is None:
                detail = "no continuation"
            else:
                detail = f"heading dot {nxt_score:.4f}"
            failures.append(f"{name} track {track_index}: joint at {nxt} {detail}")
            return failures
        chosen = nxt_choice

    expected_keys = [_point_key(station_point(node, track_index)) for node in nodes]
    cursor = 0
    for node_index, expected in enumerate(expected_keys):
        while cursor < len(path) and path[cursor] != expected:
            cursor += 1
        if cursor >= len(path):
            failures.append(
                f"{name} track {track_index}: node {node_index} not on the chain "
                f"(wanted {expected})"
            )
            continue
        tangent = node_tangent(nodes[node_index])
        if _dot(travel_tangent[expected], tangent) < TANGENT_DOT:
            failures.append(
                f"{name} track {track_index}: node {node_index} heading dot "
                f"{_dot(travel_tangent[expected], tangent):.4f}"
            )
    return failures


def check_spacing(name, nodes_and_tracks):
    failures = []
    for node, present in nodes_and_tracks:
        present = sorted(present)
        for track_index in present:
            if track_index + 1 not in present:
                continue
            left = station_point(node, track_index)
            right = station_point(node, track_index + 1)
            # Actual rails were already required to pass through these stations.
            delta = (
                float(right[0] - left[0]),
                float(right[1] - left[1]),
                float(right[2] - left[2]),
            )
            expected = lateral_step(node)
            error = max(abs(delta[i] - expected[i]) for i in range(3))
            if error > 0.5:
                failures.append(
                    f"{name}: spacing at {node[1]} h={node[2]} tracks "
                    f"{track_index}->{track_index + 1} off by {error}"
                )
            if node[1] == "0fw":
                distance = math.hypot(delta[0], delta[1])
                if abs(distance - 192) > 0.5:
                    failures.append(
                        f"{name}: 0fw spacing {distance} != 192 "
                        f"at heading {node[2]}"
                    )
    return failures


def track_runs(modes):
    """Consecutive pieces on which each track index exists."""

    pieces = {}
    for piece_index, mode in enumerate(modes):
        for track_index in range(-mode[0], mode[1] + 1):
            pieces.setdefault(track_index, []).append(piece_index)
    runs = []
    for track_index, piece_indices in pieces.items():
        start = previous = piece_indices[0]
        for piece_index in piece_indices[1:] + [None]:
            if piece_index is not None and piece_index == previous + 1:
                previous = piece_index
                continue
            runs.append((track_index, start, previous))
            if piece_index is not None:
                start = previous = piece_index
    return runs


def present_at_nodes(modes):
    """Track indices that have a station on each backbone node."""

    count = len(modes)
    present = [set() for _ in range(count + 1)]
    for piece_index, mode in enumerate(modes):
        indices = set(range(-mode[0], mode[1] + 1))
        present[piece_index] |= indices
        present[piece_index + 1] |= indices
    return present


def run_case(name, start, pieces, models):
    node = start
    steps = [
        {
            "node": node,
            "model": "",
            "current_run": [pieces[0][1], 0, {}],
        }
    ]
    nodes = [node]
    modes = []
    for index, (authored, mode) in enumerate(pieces):
        model = models[authored]
        if node[1] not in _entry_directions(*authored):
            return [f"{name}: entered {authored} from {node[1]}, which is not a real entry"]
        node = advance(node, model, mode)
        nodes.append(node)
        modes.append(mode)
        next_mode = pieces[index + 1][1] if index + 1 < len(pieces) else mode
        steps.append(
            {
                "node": node,
                "model": model,
                "current_run": [next_mode, 0, {}],
            }
        )

    placed = []
    vmfpy.add_entity = placed.append
    lines.write_bezier_points = lambda *_args, **_kwargs: None
    try:
        track.write_track_from_trackhammer_steps(steps)
    except Exception as error:
        return [f"{name}: {type(error).__name__}: {error}"]

    allowed = set()
    for track_index, first_piece, last_piece in track_runs(modes):
        for boundary in (nodes[first_piece], nodes[last_piece + 1]):
            allowed.add(
                endpoint_key(
                    station_point(boundary, track_index),
                    node_tangent(boundary),
                )
            )
    failures = [
        f"{name}: {problem}"
        for problem in audit_props(placed, track.track_model_library, allowed)
    ]
    return failures


def _entry_directions(start_direction, end_direction):
    entries = set()
    if start_direction in NODE_DIRS:
        entries.add(start_direction)
    if end_direction in NODE_DIRS and end_direction != start_direction:
        entries.add(end_direction)
    if start_direction in OTHER_4:
        entries.add(OTHER_4[start_direction])
    if end_direction in OTHER_4 and end_direction != start_direction:
        entries.add(OTHER_4[end_direction])
    return entries


def single_piece_cases(models):
    cases = []
    for authored, _name in models.items():
        along_start, _along_end, exact = grid_offset(*authored)
        if along_start is None:
            # 8lt↔8rt: tangents are opposite, so the snap cannot close the joint.
            continue
        if not exact:
            continue
        for entry in sorted(_entry_directions(*authored)):
            for heading in HEADINGS:
                for mode in MODES:
                    label = (
                        f"{authored[0]}->{authored[1]} from {entry} "
                        f"h={heading} mode={mode}"
                    )
                    origin = (heading * 16, (mode[0] - mode[1]) * 16, 32)
                    cases.append(
                        (
                            label,
                            make_node(entry, heading, origin),
                            [(authored, mode)],
                        )
                    )
    return cases


def chain_cases(models):
    """Multi-piece runs: S-curves, 90° swings, 45° hand changes, run boundaries."""

    chains = {
        "s-curve": [
            ("0fw", "2lt"),
            ("2lt", "0fw"),
            ("0fw", "2rt"),
            ("2rt", "0fw"),
            ("0fw", "1lt"),
            ("0fw", "1lt"),  # reverse back through the same shape to 0fw
        ],
        "ninety": [
            ("0fw", "8rt"),
            ("0fw", "2rt"),
            ("2rt", "8rt"),
            ("0fw", "8lt"),
            ("0fw", "2lt"),
            ("2lt", "8lt"),
            ("0fw", "4rt"),
            ("4rt", "8rt"),
        ],
        "reverse-curve-90": [
            ("0fw", "8lt"),
            ("0fw", "4lt"),
            ("4rt", "2rt"),  # hand change off the 4lt node
            ("2rt", "0fw"),
            ("0fw", "8rt"),
            ("0fw", "4rt"),
            ("4lt", "0fw"),  # hand change, reverse authoring
        ],
        "run-boundary": [
            ("0fw", "1rt"),
            ("1rt", "2rt"),
            ("2rt", "1rt"),
            ("1rt", "0fw"),
            ("0fw", "4lt"),
            ("4lt", "0fw"),
        ],
    }
    # run-boundary uses a different mode on each piece; the others repeat one mode.
    boundary_modes = ((3, 2), (3, 2), (1, 0), (0, 3), (2, 1), (0, 0))
    cases = []
    for heading in HEADINGS:
        for mode in MODES:
            for chain_name, authored_steps in chains.items():
                if chain_name == "run-boundary":
                    continue
                missing = [step for step in authored_steps if step not in models]
                if missing:
                    continue
                cases.append(
                    (
                        f"chain {chain_name} h={heading} mode={mode}",
                        make_node("0fw", heading, (1000, -500, 32)),
                        [(step, mode) for step in authored_steps],
                    )
                )
        steps = chains["run-boundary"]
        cases.append(
            (
                f"chain run-boundary h={heading}",
                make_node("0fw", heading, (1000, -500, 64)),
                list(zip(steps, boundary_modes)),
            )
        )
    return cases


def check_legacy_table():
    failures = []
    for pair, expected in LEGACY_OFFSETS.items():
        got = track.get_offset_forward_for_parallel_on_right(*pair)
        if got != expected:
            failures.append(f"offset {pair[0]}->{pair[1]} is {got}, table says {expected}")
        # The table is stored low-angle to high-angle, so either call order
        # returns that same pair. Travel order is applied when the segment is placed.
        reverse = track.get_offset_forward_for_parallel_on_right(pair[1], pair[0])
        if reverse != expected:
            failures.append(
                f"offset {pair[1]}->{pair[0]} is {reverse}, table says {expected}"
            )
    return failures


def _code_stagger(start_direction, end_direction):
    """Stagger the placer actually uses, along this traversal."""

    along_low, along_high = track.get_offset_forward_for_parallel_on_right(
        start_direction, end_direction
    )
    if int(start_direction[0]) > int(end_direction[0]):
        return -along_high, -along_low
    return along_low, along_high


def rounded_residuals(outer_tracks=3):
    """How far the outermost parallel track sits from a perfect (non-grid) stagger.

    Reported for pairs the table does not hit exactly: the snap to 16 units,
    and 8lt↔8rt, where the tangents are opposite so the nearest grid value is 0.
    """

    rows = []
    worst = 0.0
    worst_name = ""
    for start_direction in ALL_DIRS:
        for end_direction in ALL_DIRS:
            if start_direction == end_direction:
                continue
            exact_start, exact_end, exact = grid_offset(start_direction, end_direction)
            used_start, used_end = _code_stagger(start_direction, end_direction)
            if exact_start is None:
                right_start = track.move_in_trackspace(0, start_direction, 1)
                right_end = track.move_in_trackspace(0, end_direction, 1)
                forward_start = track.move_in_trackspace(1, start_direction, 0)
                forward_end = track.move_in_trackspace(1, end_direction, 0)
                remain_x = (right_end[0] - right_start[0]) - (
                    used_start * forward_start[0] + used_end * forward_end[0]
                )
                remain_y = (right_end[1] - right_start[1]) - (
                    used_start * forward_start[1] + used_end * forward_end[1]
                )
                per_track = math.hypot(remain_x, remain_y)
                note = "opposite tangents, snap is 0"
            else:
                if exact and (used_start, used_end) == (exact_start, exact_end):
                    continue
                forward_start = track.move_in_trackspace(1, start_direction, 0)
                forward_end = track.move_in_trackspace(1, end_direction, 0)
                delta_start = used_start - exact_start
                delta_end = used_end - exact_end
                remain_x = delta_start * forward_start[0] + delta_end * forward_end[0]
                remain_y = delta_start * forward_start[1] + delta_end * forward_end[1]
                per_track = math.hypot(remain_x, remain_y)
                note = (
                    f"exact ({exact_start:.1f}, {exact_end:.1f}) "
                    f"used ({used_start}, {used_end})"
                )
            miss = per_track * outer_tracks
            rows.append((miss, f"{start_direction}->{end_direction}", note, per_track))
            if miss > worst:
                worst = miss
                worst_name = f"{start_direction}->{end_direction}"
    rows.sort(reverse=True)
    return rows, worst, worst_name


def main():
    random.seed(0)
    models = register_library()
    right = track.move_in_trackspace(0, "0fw", 1)
    if (int(right[0]), int(right[1])) != (0, 192):
        print(f"0fw lateral offset is {right}, expected (0, 192)")
        return 1
    failures = check_legacy_table()
    cases = single_piece_cases(models) + chain_cases(models)
    residuals, worst, worst_name = rounded_residuals()
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        for name, start, pieces in cases:
            failures.extend(run_case(name, start, pieces, models))
            if len(failures) > 40:
                break

    print(
        f"parallel geometry: {len(cases)} exact-join cases, "
        f"{len(failures)} failures"
    )
    print(
        f"rounded-stagger residual, outermost of 3 tracks each side: "
        f"{worst:.1f} units on {worst_name}"
    )
    print("rounded families (ideal joint vs 16-unit snap):")
    shown = set()
    for miss, name, note, per_track in residuals:
        family = tuple(sorted(name.split("->")))
        if family in shown:
            continue
        shown.add(family)
        print(f"  {name}: {miss:.1f} units at 3 tracks ({per_track:.1f} per track); {note}")
    noise = [
        line
        for line in log.getvalue().splitlines()
        if "Not divisible" in line or "Invalid combination" in line or "ValueError" in line
    ]
    if noise:
        print("library noise:")
        for line in noise[:10]:
            print(f"  {line}")
    if failures:
        print("failures:")
        for line in failures[:40]:
            print(f"  {line}")
        return 1
    print("exact joins met in position, heading, and 192-unit spacing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
