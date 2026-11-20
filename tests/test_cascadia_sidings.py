"""gm_cascadia parallel sidings.

They are not in the TrakPak3 manifest. catalog_models appends
data/cascadia_models.json, and select_switch then prefers those
minr2048 pieces for 2lt, 2rt, 4lt, and 4rt.
"""

import json
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import lines, tools, track, vmfpy
from railmancer.joincheck import (
    audit_props,
    endpoint_key,
    library_from_prop_names,
    parse_vmf_track_props,
)
from railmancer.switches import (
    catalog_models,
    geometry_from_model,
    place_transition,
    register_switch_library,
    select_switch,
    zone_length,
)
from railmancer.trakpak_manifest import load_manifest

PREFIX = "models/trakpak3_rsg/switches/sidings/"

# direction, hand, stem, short, long, track_delta
EXPECTED = (
    ("2lt", "left", "p2lt_left_minr2048_+0704x-0352_+1184x-0832", 704, 1280, -1),
    ("2lt", "right", "p2lt_right_minr2048_+0704x-0352_+1376x-0448", 704, 1280, 1),
    ("2rt", "left", "p2rt_left_minr2048_+0704x+0352_+1376x+0448", 704, 1280, -1),
    ("2rt", "right", "p2rt_right_minr2048_+0704x+0352_+1184x+0832", 704, 1280, 1),
    ("4lt", "left", "p4lt_left_minr2048_+0512x-0512_+0880x-1168", 512, 1024, -1),
    ("4lt", "right", "p4lt_right_minr2048_+0512x-0512_+1168x-0880", 512, 1024, 1),
    ("4rt", "left", "p4rt_left_minr2048_+0512x+0512_+1168x+0880", 512, 1024, -1),
    ("4rt", "right", "p4rt_right_minr2048_+0512x+0512_+0880x+1168", 512, 1024, 1),
)

STOCK = {
    ("0fw", "left"): "p0fw_left_minr2048_+0768x00000_+1536x-0192",
    ("0fw", "right"): "p0fw_right_minr2048_+0768x00000_+1536x+0192",
    ("1lt", "left"): "p1lt_left_minr2048_+0768x-0192_+1488x-0576",
    ("1lt", "right"): "p1lt_right_minr2048_+0768x-0192_+1584x-0192",
    ("1rt", "left"): "p1rt_left_minr2048_+0768x+0192_+1584x+0192",
    ("1rt", "right"): "p1rt_right_minr2048_+0768x+0192_+1488x+0576",
}


def _paths():

    paths = []
    for _direction, _hand, stem, _short, _long, _delta in EXPECTED:
        paths.append(PREFIX + stem + "_dv.mdl")
        paths.append(PREFIX + stem + "_mn.mdl")
    return paths


class _Library(dict):

    def __getitem__(self, key):
        if key not in self and "straights" in str(key):
            parsed = track.process_file(key)
            if parsed:
                self[key] = parsed[0]
        return dict.__getitem__(self, key)


def _vmf(props):

    blocks = []
    for index, prop in enumerate(props, start=1):
        pos = prop["pos"]
        ang = prop["ang"]
        classname = prop.get("classname") or "prop_static"
        lines_out = [
            "entity",
            "{",
            f'"id" "{index}"',
            f'"classname" "{classname}"',
            f'"model" "{prop["mdl"]}"',
            f'"origin" "{float(pos[0])} {float(pos[1])} {float(pos[2])}"',
            f'"angles" "{float(ang[0])} {float(ang[1])} {float(ang[2])}"',
        ]
        if prop.get("model_div"):
            lines_out.append(f'"model_div" "{prop["model_div"]}"')
        lines_out.append("}")
        blocks.append("\n".join(lines_out))
    return "\n".join(blocks) + "\n"


def _open_ends(origin, direction, heading, before, after, total):

    tangent = tools.rot_orth(track.get_heading(direction), heading)
    allowed = set()
    for mode, station in ((before, 0), (after, total)):
        for track_index in range(-mode[0], mode[1] + 1):
            point = track.updated_position(
                origin,
                track.move_in_trackspace(station, direction, track_index),
                heading,
            )
            allowed.add(endpoint_key(point, tangent))
    return allowed


class CascadiaSidingTests(unittest.TestCase):

    def test_each_stem_parses_exact_and_condensed(self):

        for direction, hand, stem, short, long, delta in EXPECTED:
            record = geometry_from_model(PREFIX + stem + "_dv.mdl")
            self.assertEqual(record["Direction"], direction, stem)
            self.assertEqual(record["hand"], hand, stem)
            self.assertTrue(record["exact"], stem)
            self.assertTrue(record["condensed"], stem)
            self.assertEqual(record["short"], short, stem)
            self.assertEqual(record["long"], long, stem)
            self.assertEqual(record["track_delta"], delta, stem)
            self.assertEqual(record["radius"], 2048, stem)

    def test_select_switch_picks_cascadia_for_2_and_4(self):

        for direction, hand, stem, short, long, delta in EXPECTED:
            chosen = select_switch(direction, hand)
            self.assertTrue(chosen["dv"].endswith(stem + "_dv.mdl"), chosen["dv"])
            self.assertEqual(chosen["short"], short)
            self.assertEqual(chosen["long"], long)
            self.assertEqual(chosen["track_delta"], delta)

    def test_p0_and_p1_selections_are_unchanged(self):

        for (direction, hand), stem in STOCK.items():
            chosen = select_switch(direction, hand)
            self.assertTrue(chosen["dv"].endswith(stem + "_dv.mdl"), chosen["dv"])
            self.assertEqual(chosen["short"], 768)
            self.assertEqual(chosen["long"], 1536)
            self.assertEqual(chosen["radius"], 2048)
            self.assertTrue(chosen["condensed"])

    def test_catalog_appends_the_paths_once(self):

        with open(os.path.join(ROOT, "data", "cascadia_models.json"), encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertIn("gm_cascadia", payload["note"])
        self.assertIn("not part of TrakPak3", payload["note"])
        paths = _paths()
        self.assertEqual(payload["models"], paths)

        manifest = load_manifest()
        base = [
            name
            for name, entry in manifest["models"].items()
            if entry.get("family") == "sidings" or "/switches/sidings/" in name
        ]
        catalog = catalog_models()
        self.assertTrue(set(base).isdisjoint(paths))
        self.assertEqual(len(catalog), len(set(catalog)))
        self.assertEqual(catalog[-len(paths) :], paths)
        self.assertEqual(len(catalog), len(base) + len(paths))

    def test_vmf_accepts_them_and_a_ladder_hashes(self):

        props = [
            {"mdl": path, "pos": [0, 0, 0], "ang": (0, 0, 0)} for path in _paths()
        ]
        _library, unknown = library_from_prop_names(props)
        self.assertEqual(unknown, [])

        track.track_model_library = _Library()
        register_switch_library()
        lines.write_bezier_points = lambda *_args, **_kwargs: None
        origin = (0.0, 0.0, 0.0)
        for direction, before, after in (
            ("4lt", (0, 0), (1, 0)),
            ("4lt", (0, 0), (0, 1)),
            ("4rt", (0, 0), (1, 0)),
            ("4rt", (0, 0), (0, 1)),
            ("2lt", (0, 0), (0, 1)),
            ("2rt", (1, 0), (0, 0)),
            # 704/1280 is not 2:1, so a side swap used to cross the main legs.
            ("2lt", (0, 1), (1, 0)),
            ("2rt", (1, 0), (0, 1)),
        ):
            heading = 0
            total = zone_length(before, after, direction)
            placed = []
            vmfpy.add_entity = placed.append
            place_transition(origin, direction, heading, before, after)
            props = [prop for prop in placed if isinstance(prop, dict)]
            allowed = _open_ends(origin, direction, heading, before, after, total)
            problems = audit_props(props, track.track_model_library, allowed)
            self.assertEqual(problems, [], f"{direction} {before}->{after} {problems}")
            parsed = parse_vmf_track_props(_vmf(props))
            library, unknown = library_from_prop_names(parsed)
            self.assertEqual(unknown, [], direction)
            self.assertEqual(audit_props(parsed, library, allowed), [], direction)


if __name__ == "__main__":
    unittest.main()
