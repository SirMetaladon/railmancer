"""Switch ladders at every change in parallel-track count.

The hash is the owner's test: a switch contributes three endpoints (point,
main leg, diverging leg) and every endpoint appears exactly twice, except
the open ends of the run, which sit on move_in_trackspace spacing.
"""

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import lines, track, tools, vmfpy
from railmancer.joincheck import audit_props, endpoint_key, position_key
from railmancer.switches import (
    SwitchGeometryError,
    place_transition,
    register_switch_library,
    select_switch,
    zone_length,
)

def _all_modes():
    counts = [(left, right) for left in range(4) for right in range(4)]
    return [(before, after) for before in counts for after in counts if before != after]


MODES = _all_modes()
# Overlapped zone length on 0fw. short=768, long=1536 from the condensed siding.
EXPECTED_0FW = {
    ((3, 0), (0, 3)): 4608,
    ((2, 1), (1, 2)): 1536,
    ((0, 0), (1, 1)): 2304,
}

ORIENTATIONS = (
    ("0fw", 0),
    ("0fw", 90),
    ("0fw", -90),
    ("1lt", 0),
    ("1lt", 180),
    ("2rt", 270),
    ("2lt", 90),
)


class _Library(dict):
    def __getitem__(self, key):
        if key not in self and "straights" in str(key):
            parsed = track.process_file(key)
            if parsed:
                self[key] = parsed[0]
        return dict.__getitem__(self, key)


def _install_library():
    track.track_model_library = _Library()
    register_switch_library()
    lines.write_bezier_points = lambda *_args, **_kwargs: None


def _station(origin, direction, heading, station, track_index):
    return track.updated_position(
        origin, track.move_in_trackspace(station, direction, track_index), heading
    )


def _open_ends(origin, direction, heading, before, after, total):
    tangent = tools.rot_orth(track.get_heading(direction), heading)
    allowed = set()
    for mode, station in ((before, 0), (after, total)):
        for track_index in range(-mode[0], mode[1] + 1):
            allowed.add(
                endpoint_key(
                    _station(origin, direction, heading, station, track_index),
                    tangent,
                )
            )
    return allowed


def _on_grid(props):
    problems = []
    for prop in props:
        point = position_key(prop["pos"])
        if any(component % 16 != 0 for component in point):
            problems.append(f"off grid {prop.get('mdl', '')} at {point}")
    return problems


def _transition_case(before, after, direction, heading):
    name = f"{before[0]}L{before[1]}R->{after[0]}L{after[1]}R {direction} h{heading}"
    origin = (0.0, 0.0, 0.0)
    total = zone_length(before, after, direction)
    if total <= 0 or total % 16 != 0:
        return [f"{name}: zone length {total}"]
    if direction == "0fw" and (before, after) in EXPECTED_0FW:
        expected = EXPECTED_0FW[(before, after)]
        if total != expected:
            return [f"{name}: zone {total}, expected {expected}"]
    placed = []
    vmfpy.add_entity = placed.append
    place_transition(origin, direction, heading, before, after)
    allowed = _open_ends(origin, direction, heading, before, after, total)
    failures = [f"{name}: {problem}" for problem in _on_grid(placed)]
    failures.extend(
        f"{name}: {problem}"
        for problem in audit_props(placed, track.track_model_library, allowed)
    )
    switches = [prop for prop in placed if prop.get("classname") == "tp3_switch"]
    if not switches:
        failures.append(f"{name}: no switch was placed")
    for prop in switches:
        if "model_div" not in prop:
            failures.append(f"{name}: switch has no diverging model")
        if not prop["mdl"].endswith("_mn.mdl"):
            failures.append(f"{name}: main model was {prop['mdl']}")
        if not prop["model_div"].endswith("_dv.mdl"):
            failures.append(f"{name}: diverging model was {prop.get('model_div')}")
    return failures


def _length_guards():
    failures = []
    for bad in (-16, -1, 24, 8):
        try:
            track.create_straight((0, 0, 0), bad, "0fw", 0)
        except ValueError:
            continue
        failures.append(f"create_straight accepted {bad}")
    try:
        track.create_straight((0, 0, 0), 0, "0fw", 0)
    except ValueError as exc:
        failures.append(f"create_straight rejected a zero length: {exc}")
    return failures


def _model_choice():
    failures = []
    chosen = select_switch("0fw", "left")
    if chosen["short"] >= chosen["long"]:
        failures.append("0fw left switch is not condensed")
    if "minr2048" not in chosen["dv"] or "+0768x" not in chosen["dv"]:
        failures.append(f"unexpected 0fw left model {chosen['dv']}")
    right = select_switch("0fw", "right")
    if right["track_delta"] != 1 or right["short"] != chosen["short"] or right["long"] != chosen["long"]:
        failures.append(
            f"0fw right lengths {right['short']}/{right['long']} delta {right['track_delta']}"
        )
    for direction in ("1lt", "1rt", "2lt", "2rt"):
        for hand in ("left", "right"):
            spec = select_switch(direction, hand)
            if not spec["condensed"] or spec["short"] != 768 or spec["long"] != 1536:
                failures.append(
                    f"{direction} {hand} -> short {spec['short']} long {spec['long']} {spec['dv']}"
                )
    try:
        select_switch("4lt", "left")
    except SwitchGeometryError:
        pass
    else:
        failures.append("4lt left was accepted; its diverging end is off the parallel grid")
    return failures


def _writer_hook():
    """The pathfinder step list has to place the fill and the ladder."""

    direction, heading = "1lt", 90
    before, after = (2, 1), (1, 2)
    fill = 64
    zone = zone_length(before, after, direction)
    origin = (256.0, -128.0, 0.0)
    start = (origin, direction, heading, False)
    after_fill_pos = track.updated_position(
        origin, track.move_in_trackspace(fill, direction), heading
    )
    after_fill = (after_fill_pos, direction, heading, False)
    end_pos = track.updated_position(
        after_fill_pos, track.move_in_trackspace(zone, direction), heading
    )
    end = (end_pos, direction, heading, False)
    steps = [
        {"model": "", "node": start, "current_run": [before, 0, {}]},
        {
            "model": "",
            "node": after_fill,
            "current_run": [before, 0, {}],
            "tangent_fill": fill,
        },
        {
            "model": "",
            "node": end,
            "current_run": [after, 0, {}],
            "switch_zone": (before, after),
        },
    ]
    placed = []
    vmfpy.add_entity = placed.append
    track.write_track_from_trackhammer_steps(steps)
    allowed = _open_ends(origin, direction, heading, before, after, fill + zone)
    failures = [f"writer hook: {problem}" for problem in _on_grid(placed)]
    failures.extend(
        f"writer hook: {problem}"
        for problem in audit_props(placed, track.track_model_library, allowed)
    )
    return failures


def _bounds_case():
    from railmancer import cfg, trackhammer

    cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))
    trackhammer.initialize()
    trackhammer.set_border_override(lambda point: abs(point[0]) < 500 and abs(point[1]) < 500)
    trackhammer.BlockHorizontal = 200
    zone = zone_length((0, 0), (0, 3), "0fw")
    outside = trackhammer.corridor_is_blocked((0, 0, 0), "0fw", 0, (0, 3), zone)
    inside = not trackhammer.corridor_is_blocked((0, 0, 0), "0fw", 0, (0, 0), 256)
    failures = []
    if not outside:
        failures.append("a 3-right ladder inside a 500-unit border was accepted")
    if not inside:
        failures.append("the mainline itself was rejected inside the border")
    stub = zone_length((3, 0), (0, 1), "0fw", {"left": "stub", "right": "switch"})
    full = zone_length((3, 0), (0, 1), "0fw")
    if stub >= full:
        failures.append(f"stubbing the merge did not shorten the zone ({stub} vs {full})")
    return failures


def main():
    _install_library()
    failures = _length_guards() + _model_choice() + _writer_hook() + _bounds_case()
    cases = 0
    for before, after in MODES:
        for direction, heading in ORIENTATIONS:
            cases += 1
            failures.extend(_transition_case(before, after, direction, heading))
            if len(failures) > 30:
                break
        if len(failures) > 30:
            break
    print(f"switch ladders: {cases} transitions, {len(failures)} failures")
    for line in failures[:40]:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
