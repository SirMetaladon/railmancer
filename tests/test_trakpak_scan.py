"""Parser checks for the TrakPak3 filename scanner.

These do not download anything. They use the committed manifest and the
same process_file the scanner calls.
"""

import os
import unittest

from railmancer import track
from railmancer.trakpak_manifest import install_manifest_library, load_manifest
from tools.scan_trakpak3 import (
    HAND_FIXED_ROUTE,
    PATHFINDER_RADII,
    cross_check,
    family_of,
    is_rsg_track_model,
    parse_model,
)

STRAIGHT = "models/trakpak3_rsg/straights/s0384_0fw_0pg_+0384x00000x0000.mdl"
CURVE = "models/trakpak3_rsg/arcs/r6144/a0fw_8lt_left_311pg_+6144x-6144x+300up.mdl"
BEND = "models/trakpak3_rsg/bends/b0fw_left_minr2048_0pg_+1536x-0192x0000.mdl"
ONE_RT = "models/trakpak3_rsg/straights/s1024_1rt_303pg_+1024x+0256x+032up.mdl"


class TrakpakScanTests(unittest.TestCase):

    def test_straight_and_curve_match_process_file(self):

        routes, reason = parse_model(STRAIGHT)
        self.assertEqual(reason, "")
        self.assertEqual(routes[0]["StartDirection"], "0fw")
        self.assertEqual(routes[0]["Move"], [-384, 0, 0])
        self.assertEqual(routes[0]["Radius"], 0)
        self.assertEqual(family_of(STRAIGHT), "straights")

        routes, reason = parse_model(CURVE)
        self.assertEqual(reason, "")
        route = routes[0]
        self.assertEqual(route["StartDirection"], "0fw")
        self.assertEqual(route["EndDirection"], "8lt")
        self.assertEqual(route["Radius"], 6144)
        self.assertEqual(route["RealGrade"], 3.11)
        self.assertEqual(route["Move"][0], -6144)
        self.assertEqual(route["Move"][1], -6144)
        self.assertEqual(route["Move"][2], 300)

    def test_one_in_four_straight_matches_the_hardcoded_slope(self):

        routes, reason = parse_model(ONE_RT)
        self.assertEqual(reason, "")
        change_x = -routes[0]["Move"][0]
        change_y = routes[0]["Move"][1]
        self.assertEqual(change_y, 0.25 * change_x)

    def test_unknown_family_is_reported(self):

        self.assertTrue(is_rsg_track_model(BEND))
        routes, reason = parse_model(BEND)
        self.assertIsNone(routes)
        self.assertIn("No track-processing support", reason)
        self.assertFalse(is_rsg_track_model("models/trakpak3_rsg_bridge/arcs/r2048/x.mdl"))
        self.assertFalse(is_rsg_track_model("models/trakpak3_rsg/spl/bridges/deck.mdl"))

    def test_manifest_covers_the_hand_fixed_route_and_flags_extra_radii(self):

        manifest = load_manifest()
        self.assertEqual(manifest["source"]["kind"], "github")
        self.assertTrue(manifest["source"]["commit"])
        for model in HAND_FIXED_ROUTE:
            self.assertIn(model, manifest["models"], model)
        notes = cross_check(manifest["models"], manifest["unparsed"])
        joined = "\n".join(notes)
        self.assertIn("2240", joined)
        self.assertTrue(any(radius not in PATHFINDER_RADII for radius in (2240, 8384)))
        bend_names = [item["model"] for item in manifest["unparsed"] if item["family"] == "bends"]
        self.assertIn(BEND, bend_names)

    def test_manifest_library_places_a_real_straight(self):

        count = install_manifest_library()
        self.assertGreater(count, 1000)
        model = "models/trakpak3_rsg/straights/s1024_0fw_0pg_+1024x00000x0000.mdl"
        self.assertIn(model, track.track_model_library)
        # Switches have two routes and stay out, same as build_track_library.
        switches = [
            name
            for name in track.track_model_library
            if "/switches/" in name
        ]
        self.assertEqual(switches, [])
        node = ([0, 0, 0], "0fw", 0, False)
        result = track.get_new_node_from_node_and_model(model, node, False, 0, 0)
        self.assertEqual(int(result[0][0]), -1024)


if __name__ == "__main__":
    unittest.main()
