"""The 2-left, 0-right route, checked against c_fully_fixed.vmf.

That file is the fully hand-fixed map of this route: the straights that
were still wrong in the first edit, including both 2rt fillers, and the
end frog moved onto the rail. Comparison is the two endpoints of each
prop. A flipped prop still matches. The frog and the cones are endpoints
too, and the end frog has to sit on (12432, -13040, -11020).
"""

import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import lines, track, tools, vmfpy
from railmancer.joincheck import audit_marked_props, audit_props, endpoint_key, prop_endpoints

START = ((7568.0, 3552.0, -13040.0), "0fw", -90, False)
MODE = (2, 0)

# Backbone, center track, in travel order. The same model is reused when the
# pathfinder laid the same piece twice.
ROUTE = [
    "models/trakpak3_rsg/straights/s2048_0fw_312pg_+2048x00000x+064up.mdl",
    "models/trakpak3_rsg/arcs/r8192/a0fw_4lt_left_311pg_+5920x-2400x+204up.mdl",
    "models/trakpak3_rsg/arcs/r4096/a2rt_4rt_right_-311pg_+1248x+0896x-048dn.mdl",
    "models/trakpak3_rsg/straights/s0384_2rt_279pg_+0384x+0192x+012up.mdl",
    "models/trakpak3_rsg/arcs/r8192/a1rt_2rt_right_-312pg_+1920x+0704x-064dn.mdl",
    "models/trakpak3_rsg/straights/s0128_1rt_303pg_+0128x+0032x+004up.mdl",
    "models/trakpak3_rsg/straights/s1024_1rt_303pg_+1024x+0256x+032up.mdl",
    "models/trakpak3_rsg/straights/s1536_1rt_303pg_+1536x+0384x+048up.mdl",
    "models/trakpak3_rsg/straights/s0128_1rt_303pg_+0128x+0032x+004up.mdl",
    "models/trakpak3_rsg/straights/s0768_1rt_303pg_+0768x+0192x+024up.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_1rt_right_-315pg_+1760x+0224x-056dn.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_8lt_left_311pg_+6144x-6144x+300up.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_2lt_left_314pg_+2944x-0704x+096up.mdl",
    "models/trakpak3_rsg/straights/s1024_2lt_279pg_+1024x-0512x+032up.mdl",
    "models/trakpak3_rsg/arcs/r4096/a0fw_2lt_left_-306pg_+2016x-0480x-064dn.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_8lt_left_311pg_+6144x-6144x+300up.mdl",
    "models/trakpak3_rsg/straights/s6144_0fw_312pg_+6144x00000x+192up.mdl",
    "models/trakpak3_rsg/straights/s3072_0fw_312pg_+3072x00000x+096up.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_8rt_right_311pg_+6144x+6144x+300up.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_1rt_right_315pg_+1760x+0224x+056up.mdl",
    "models/trakpak3_rsg/straights/s0128_1rt_303pg_+0128x+0032x+004up.mdl",
    "models/trakpak3_rsg/straights/s0128_1rt_303pg_+0128x+0032x+004up.mdl",
    "models/trakpak3_rsg/straights/s0512_1rt_303pg_+0512x+0128x+016up.mdl",
]

# Frog on main, cones on the two left tracks, at the start and at the end.
# The end frog is on the rail: (12432, -13040, -11020).
EXPECTED_MARKERS = (
    (7568, 3552, -13040),
    (7376, 3552, -13040),
    (7184, 3552, -13040),
    (12624, -13088, -11020),
    (12816, -13136, -11020),
    (12432, -13040, -11020),
)

# Both endpoints of every track prop in c_fully_fixed.vmf, order inside each
# pair sorted so a flipped prop still matches. Curves and straights.
EXPECTED_PIECES = [
    ((-10032, 5200, -12084), (-9520, 4176, -12052)),
    ((-10352, 8336, -12180), (-4208, 14480, -12480)),
    ((-10352, 8336, -12180), (-9648, 5392, -12084)),
    ((-10544, 8240, -12180), (-10544, 8336, -12180)),
    ((-10544, 8240, -12180), (-9840, 5296, -12084)),
    ((-10544, 8336, -12180), (-10544, 8528, -12180)),
    ((-10544, 8528, -12180), (-4400, 14672, -12480)),
    ((-10736, 8144, -12180), (-10032, 5200, -12084)),
    ((-10736, 8144, -12180), (-10736, 8336, -12180)),
    ((-10736, 8336, -12180), (-10736, 8720, -12180)),
    ((-10736, 8720, -12180), (-4592, 14864, -12480)),
    ((-1456, 14416, -12564), (80, 14032, -12612)),
    ((-1504, 14224, -12564), (32, 13840, -12612)),
    ((-1552, 14032, -12564), (-16, 13648, -12612)),
    ((-1584, 14448, -12560), (-1456, 14416, -12564)),
    ((-16, 13648, -12612), (1008, 13392, -12644)),
    ((-1632, 14256, -12560), (-1504, 14224, -12564)),
    ((-1680, 14064, -12560), (-1552, 14032, -12564)),
    ((-2352, 14640, -12536), (-1584, 14448, -12560)),
    ((-2400, 14448, -12536), (-1632, 14256, -12560)),
    ((-2448, 14256, -12536), (-1680, 14064, -12560)),
    ((-2512, -3984, -11688), (3632, -3984, -11496)),
    ((-2512, -4176, -11688), (3632, -4176, -11496)),
    ((-2512, -4368, -11688), (3632, -4368, -11496)),
    ((-2704, -4176, -11688), (-2512, -4176, -11688)),
    ((-2896, -4368, -11688), (-2512, -4368, -11688)),
    ((-4112, 14864, -12480), (-2352, 14640, -12536)),
    ((-4160, 14672, -12480), (-2400, 14448, -12536)),
    ((-4208, 14480, -12480), (-2448, 14256, -12536)),
    ((-4208, 14672, -12480), (-4160, 14672, -12480)),
    ((-4208, 14864, -12480), (-4112, 14864, -12480)),
    ((-4400, 14672, -12480), (-4208, 14672, -12480)),
    ((-4592, 14864, -12480), (-4208, 14864, -12480)),
    ((-8656, 2160, -11988), (-2512, -3984, -11688)),
    ((-8656, 2160, -11988), (-8656, 2352, -11988)),
    ((-8848, 1968, -11988), (-2704, -4176, -11688)),
    ((-8848, 1968, -11988), (-8848, 2160, -11988)),
    ((-8848, 2160, -11988), (-8848, 2256, -11988)),
    ((-9040, 1776, -11988), (-2896, -4368, -11688)),
    ((-9040, 1776, -11988), (-9040, 2160, -11988)),
    ((-9136, 4368, -12052), (-8656, 2352, -11988)),
    ((-9328, 4272, -12052), (-8848, 2256, -11988)),
    ((-9520, 4176, -12052), (-9040, 2160, -11988)),
    ((-9648, 5392, -12084), (-9136, 4368, -12052)),
    ((-9840, 5296, -12084), (-9328, 4272, -12052)),
    ((1008, 13392, -12644), (1136, 13360, -12648)),
    ((1056, 13584, -12644), (1184, 13552, -12648)),
    ((1104, 13776, -12644), (1232, 13744, -12648)),
    ((1136, 13360, -12648), (3056, 12656, -12712)),
    ((1184, 13552, -12648), (1280, 13528, -12648)),
    ((1232, 13744, -12648), (1424, 13696, -12648)),
    ((12432, -13040, -11020), (12560, -12528, -11036)),
    ((12560, -12528, -11036), (12592, -12400, -11040)),
    ((12592, -12400, -11040), (12624, -12272, -11044)),
    ((12624, -12272, -11044), (12848, -10512, -11100)),
    ((12624, -13088, -11020), (12752, -12576, -11036)),
    ((12752, -12576, -11036), (12784, -12448, -11040)),
    ((12784, -12448, -11040), (12816, -12320, -11044)),
    ((1280, 13528, -12648), (3200, 12824, -12712)),
    ((12816, -12320, -11044), (13040, -10560, -11100)),
    ((12816, -13136, -11020), (12944, -12624, -11036)),
    ((12944, -12624, -11036), (12976, -12496, -11040)),
    ((12976, -12496, -11040), (13008, -12368, -11044)),
    ((13008, -12368, -11044), (13232, -10608, -11100)),
    ((13040, -10512, -11100), (13040, -10320, -11100)),
    ((13040, -10560, -11100), (13040, -10512, -11100)),
    ((13232, -10512, -11100), (13232, -10128, -11100)),
    ((13232, -10608, -11100), (13232, -10512, -11100)),
    ((1424, 13696, -12648), (3344, 12992, -12712)),
    ((3056, 12656, -12712), (3152, 12608, -12712)),
    ((3152, 12608, -12712), (3536, 12416, -12724)),
    ((32, 13840, -12612), (1056, 13584, -12644)),
    ((3200, 12824, -12712), (3248, 12800, -12712)),
    ((3248, 12800, -12712), (3632, 12608, -12724)),
    ((3344, 12992, -12712), (3728, 12800, -12724)),
    ((3536, 12416, -12724), (4784, 11520, -12772)),
    ((3632, -3984, -11496), (6704, -3984, -11400)),
    ((3632, -4176, -11496), (6704, -4176, -11400)),
    ((3632, -4368, -11496), (6704, -4368, -11400)),
    ((3632, 12608, -12724), (4880, 11712, -12772)),
    ((3728, 12800, -12724), (4976, 11904, -12772)),
    ((4784, 11520, -12772), (7184, 5600, -12976)),
    ((4880, 11712, -12772), (4928, 11664, -12772)),
    ((4928, 11664, -12772), (4976, 11616, -12772)),
    ((4976, 11616, -12772), (7376, 5696, -12976)),
    ((4976, 11904, -12772), (5072, 11808, -12772)),
    ((5072, 11808, -12772), (5168, 11712, -12772)),
    ((5168, 11712, -12772), (7568, 5792, -12976)),
    ((6704, -3984, -11400), (7088, -3984, -11400)),
    ((6704, -4176, -11400), (6896, -4176, -11400)),
    ((6704, -4368, -11400), (12848, -10512, -11100)),
    ((6896, -4176, -11400), (13040, -10320, -11100)),
    ((7088, -3984, -11400), (13232, -10128, -11100)),
    ((7184, 3552, -13040), (7184, 5600, -12976)),
    ((7376, 3552, -13040), (7376, 5600, -12976)),
    ((7376, 5600, -12976), (7376, 5696, -12976)),
    ((7568, 3552, -13040), (7568, 5600, -12976)),
    ((7568, 5600, -12976), (7568, 5792, -12976)),
    ((80, 14032, -12612), (1104, 13776, -12644)),
]


class _Library(dict):
    """Parse a filler straight the first time the writer asks for its filename."""

    def __getitem__(self, key):
        if key not in self and "straights" in str(key):
            parsed = track.process_file(key)
            if parsed:
                self[key] = parsed[0]
        return dict.__getitem__(self, key)


def _register():
    if not isinstance(track.track_model_library, _Library):
        track.track_model_library = _Library(track.track_model_library)
    for model in ROUTE:
        if model in track.track_model_library:
            continue
        parsed = track.process_file(model)
        if not parsed:
            raise RuntimeError(model)
        track.track_model_library[model] = parsed[0]


def _advance(node, model):
    end_direction = track.get_end_direction(model, node[1])
    current_direction = track.get_end_direction(model, end_direction)
    add_start, add_end = track.get_addlength(current_direction, end_direction, MODE)
    return track.get_new_node_from_node_and_model(
        model, node, False, add_start, add_end
    )


def _place():
    _register()
    node = START
    run = [MODE, 0, {}]
    steps = [{"model": "", "node": node, "current_run": run}]
    for model in ROUTE:
        node = _advance(node, model)
        steps.append({"model": model, "node": node, "current_run": run})
    placed = []
    vmfpy.add_entity = placed.append
    lines.write_bezier_points = lambda *_args, **_kwargs: None
    track.write_track_from_trackhammer_steps(steps)
    return placed, steps


def _piece_spans(props):
    spans = []
    for prop in props:
        name = prop["mdl"].replace("\\", "/")
        if "/straights/" not in name and "/arcs/" not in name and "/banked/" not in name:
            continue
        yaw = prop["ang"][1] if not isinstance(prop["ang"], (int, float)) else prop["ang"]
        start, end = prop_endpoints(prop["mdl"], prop["pos"], yaw, track.track_model_library)
        spans.append(tuple(sorted((start[0], end[0]))))
    return spans


def _open_ends(steps):
    allowed = set()
    for boundary in (steps[0]["node"], steps[-1]["node"]):
        tangent = tools.rot_orth(track.get_heading(boundary[1]), boundary[2])
        for track_index in range(-MODE[0], MODE[1] + 1):
            point = track.updated_position(
                boundary[0],
                track.move_in_trackspace(0, boundary[1], track_index),
                boundary[2],
            )
            allowed.add(endpoint_key(point, tangent))
    return allowed


def _marker_case():
    """A frog on an open end counts as the second endpoint. A miss does not."""

    library = {
        "models/trakpak3_rsg/straights/s0192_0fw_0pg_+0192x00000x0000.mdl": {
            "Move": [-192, 0, 0],
            "StartDirection": "0fw",
            "EndDirection": "0fw",
        }
    }
    props = [
        {
            "mdl": "models/trakpak3_rsg/straights/s0192_0fw_0pg_+0192x00000x0000.mdl",
            "pos": (0, 0, 0),
            "ang": (0, 0, 0),
        }
    ]
    # Frog at the near end, cone at the far end: both open ends close.
    problems, counts = audit_marked_props(props, library, [(0, 0, 0), (-192, 0, 0)])
    if problems:
        return ["markers on the rail were reported as " + "; ".join(problems)]
    if sorted(counts.values()) != [2, 2]:
        return [f"marker counts {sorted(counts.values())}, expected both ends closed"]
    missed, _counts = audit_marked_props(props, library, [(10, 0, 0)])
    if not any("does not meet" in problem for problem in missed):
        return ["a marker off the rail was accepted"]
    return []


def main():
    failures = _marker_case()
    placed, steps = _place()
    got = _piece_spans(placed)
    if sorted(got) != sorted(EXPECTED_PIECES):
        missing = [span for span in EXPECTED_PIECES if span not in got]
        extra = [span for span in got if span not in EXPECTED_PIECES]
        failures.append(
            f"endpoints differ: {len(missing)} only in the fully fixed file, {len(extra)} only in the generated route"
        )
        for span in missing[:12]:
            failures.append(f"  only in file {span}")
        for span in extra[:12]:
            failures.append(f"  only generated {span}")
    failures.extend(
        f"joint: {problem}"
        for problem in audit_props(placed, track.track_model_library, _open_ends(steps))
    )
    marked, _counts = audit_marked_props(
        placed, track.track_model_library, EXPECTED_MARKERS
    )
    failures.extend(f"marker: {problem}" for problem in marked)
    print(f"fully fixed route: {len(got)} pieces, {len(EXPECTED_MARKERS)} markers, {len(failures)} failures")
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
