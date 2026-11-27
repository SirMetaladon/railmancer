"""Markers, mileposts, warps, and momentary Trackhammer overrides.

Switch ladders do not add to the milepost distance. info_nulls sit above
the nearest plain-track origin. Mileposts and warps use the switch-stand
collapse: the side farther from the rails is kept, and a warp's yaw looks
back at the centerline.
"""

import io
import os
import random
import sys
import types
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, lines, markers, sectors, track, trackhammer, vmfpy
from railmancer.trakpak_manifest import load_manifest

MILE = 63360.0
STEP = 12672.0  # 0.2 miles
MODEL = "models/trakpak3_rsg/straights/s_marker_0fw.mdl"
FLAT = "models/trakpak3_rsg/straights/s0512_0fw_0pg_+0512x00000x0000.mdl"
GRADED = "models/trakpak3_rsg/straights/s0512_0fw_156pg_+0512x00000x+008up.mdl"
LONG = "models/trakpak3_rsg/straights/s8192_0fw_0pg_+8192x00000x0000.mdl"
CURVE = "models/trakpak3_rsg/arcs/r6144/a0fw_8lt_left_0pg_+6144x-6144x0000.mdl"
DOWN = "models/trakpak3_rsg/straights/s0512_0fw_down.mdl"
START = ((0.0, 0.0, 0.0), "0fw", 0, False)


def _node(x, y=0.0, z=10.0):

    return ((float(x), float(y), float(z)), "0fw", 0, False)


def _piece(length, grade=0):

    return {
        "Length": float(length),
        "Radius": 0,
        "StartDirection": "0fw",
        "EndDirection": "0fw",
        "GradeLevel": grade,
        "Move": [-float(length), 0, 0],
    }


class MarkerTests(unittest.TestCase):

    def setUp(self):

        self._entities = vmfpy.Entities
        self._sampled = lines.sampled_points
        self._beziers = lines.Beziers
        self._library = track.track_model_library
        self._cache = track.valid_tracks_cache
        self._base = vmfpy.base_map
        self._id = getattr(vmfpy, "ID", None)
        vmfpy.Entities = []
        vmfpy.base_map = None
        lines.sampled_points = []
        lines.Beziers = []
        track.track_model_library = {}
        track.valid_tracks_cache = {}
        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def tearDown(self):

        vmfpy.Entities = self._entities
        vmfpy.base_map = self._base
        if self._id is not None:
            vmfpy.ID = self._id
        lines.sampled_points = self._sampled
        lines.Beziers = self._beziers
        track.track_model_library = self._library
        track.valid_tracks_cache = self._cache

    def test_config_defaults(self):

        self.assertEqual(cfg.get("marker_interval_miles"), 0.2)
        self.assertEqual(cfg.get("milepost_interval_miles"), 1.0)
        self.assertEqual(cfg.get("marker_z_offset"), 64)
        self.assertEqual(cfg.get("side_offset"), 100)
        self.assertEqual(cfg.get("start_milepost"), 0)
        self.assertEqual(
            cfg.get("milepost_model"),
            "models/trakpak3_us/signs/milepost.mdl",
        )
        self.assertEqual(markers.marker_name(0.2), "mp_0_2")
        self.assertEqual(markers.marker_name(1), "mp_1_0")
        self.assertEqual(markers.marker_name(12.4, "post"), "post_12_4")

    def _route_with_a_ladder(self):

        # 0.2-mile pieces, and a ladder long enough that counting it would
        # move the 0.2-mile snap onto the first piece instead of the second.
        track.track_model_library[MODEL] = _piece(STEP)
        zone = 30000.0
        x1 = -STEP
        x_zone = x1 - zone
        x2 = x_zone - STEP
        x3 = x2 - STEP
        return [
            {"node": _node(0), "model": ""},
            {"node": _node(x1), "model": MODEL},
            {"node": _node(x_zone), "model": "", "switch_zone": ((0, 0), (0, 1))},
            {"node": _node(x2), "model": MODEL},
            {"node": _node(x3), "model": MODEL},
        ], x_zone

    def test_default_cadence_skips_the_ladder_and_sits_above_the_origin(self):

        steps, zone_x = self._route_with_a_ladder()
        pieces = markers.plain_pieces(steps)
        self.assertEqual([piece["station"] for piece in pieces], [0.0, STEP, STEP * 2])
        # The ladder's 30000 units are not in the station of the next piece.
        self.assertEqual(pieces[1]["origin"][0], zone_x)

        markers.place(steps, warps=None, milepost_interval=100)
        named = {
            ent["targetname"]: ent
            for ent in vmfpy.Entities
            if isinstance(ent, dict) and ent.get("classname") == "info_null"
        }
        self.assertEqual(
            set(named),
            {"mp_0_0", "mp_0_2", "mp_0_4", "mp_0_6"},
        )
        # 0.2 miles of plain track is the piece after the ladder, not the
        # first piece and not a point inside the ladder.
        marker = named["mp_0_2"]
        self.assertEqual(marker["pos"], (zone_x, 0, 10 + 64))
        self.assertEqual(marker["visgroup"], vmfpy.VISGROUP_MARKERS)
        self.assertEqual(named["mp_0_0"]["pos"], (0, 0, 74))
        self.assertEqual(named["mp_0_4"]["pos"][0], zone_x - STEP)

    def test_custom_cadence_z_offset_and_start_milepost(self):

        steps, _zone_x = self._route_with_a_ladder()
        cfg.CFG["marker_z_offset"] = 128
        cfg.CFG["start_milepost"] = 10
        markers.place(steps, marker_interval=0.4, milepost_interval=100)
        named = {
            ent["targetname"]: ent
            for ent in vmfpy.Entities
            if isinstance(ent, dict) and ent.get("classname") == "info_null"
        }
        self.assertEqual(set(named), {"mp_10_0", "mp_10_4"})
        self.assertNotIn("mp_10_2", named)
        self.assertEqual(named["mp_10_0"]["pos"][2], 10 + 128)
        self.assertEqual(named["mp_10_4"]["pos"][0], -STEP - 30000.0 - STEP)

    def _samples(self, parallel_y):

        points = []
        for x in range(-70000, 1000, 200):
            points.append((float(x), 0.0, 5.0))
            points.append((float(x), float(parallel_y), 5.0))
        lines.sampled_points = points

    def _mile_of_track(self):

        track.track_model_library[MODEL] = _piece(MILE)
        return [
            {"node": _node(0, z=5), "model": ""},
            {"node": _node(-MILE, z=5), "model": MODEL},
            {"node": _node(-2 * MILE, z=5), "model": MODEL},
        ]

    def test_mileposts_take_the_side_clear_of_the_parallel_track(self):

        steps = self._mile_of_track()
        # +Y is tracks_over_right at heading 0. A rail there makes +Y the
        # crowded side, so the stand pass keeps -Y.
        self._samples(192)
        markers.place(
            steps,
            warps=[{"mile": 1.0, "name": "warp_summit"}, {"mile": 9, "name": "warp_past"}],
            marker_interval=100,
        )
        sectors.collapse_quantum_switchstands()
        self.assertFalse(any(isinstance(ent, list) for ent in vmfpy.Entities))

        posts = {
            ent["targetname"]: ent
            for ent in vmfpy.Entities
            if ent.get("classname") == "prop_static"
        }
        self.assertEqual(set(posts), {"post_0_0", "post_1_0", "post_2_0"})
        self.assertEqual(posts["post_0_0"]["pos"], (0, -100, 5))
        self.assertEqual(posts["post_1_0"]["pos"], (-MILE, -100, 5))
        self.assertEqual(posts["post_0_0"]["ang"], (0, 0, 0))
        self.assertEqual(posts["post_0_0"]["mdl"], cfg.get("milepost_model"))
        self.assertEqual(posts["post_0_0"]["visgroup"], vmfpy.VISGROUP_MARKERS)
        # Mile 2 is the end of the second piece, so it snaps to that origin.
        self.assertEqual(posts["post_2_0"]["pos"], posts["post_1_0"]["pos"])

        warp = next(ent for ent in vmfpy.Entities if ent.get("targetname") == "warp_summit")
        self.assertEqual(warp["classname"], "info_teleport_destination")
        self.assertEqual(warp["pos"], (-MILE, -100, 5))
        self.assertEqual(warp["ang"], (0, 90, 0))
        self.assertFalse(any(ent.get("targetname") == "warp_past" for ent in vmfpy.Entities))

    def test_the_other_side_is_used_when_it_is_the_clear_one(self):

        self._samples(-192)
        markers.place(
            self._mile_of_track(),
            warps=[{"mile": 0, "name": "warp_zero"}],
            marker_interval=100,
            milepost_interval=1,
        )
        sectors.collapse_quantum_switchstands()
        post = next(ent for ent in vmfpy.Entities if ent.get("targetname") == "post_0_0")
        warp = next(ent for ent in vmfpy.Entities if ent.get("targetname") == "warp_zero")
        self.assertEqual(post["pos"], (0, 100, 5))
        # +Y option is turned 180, same as the second switch-stand choice.
        self.assertEqual(post["ang"], (0, 180, 0))
        self.assertEqual(warp["pos"], (0, 100, 5))
        self.assertEqual(warp["ang"], (0, -90, 0))

    def test_yaw_toward_the_centerline(self):

        origin = (0, 0, 0)
        self.assertEqual(markers._whole(markers.yaw_toward(origin, (0, -100, 0))), 90)
        self.assertEqual(markers._whole(markers.yaw_toward(origin, (0, 100, 0))), -90)
        self.assertEqual(markers._whole(markers.yaw_toward(origin, (-40, 0, 5))), 0)

    def test_vmf_keeps_info_null_and_teleport_destination(self):

        vmfpy.ID = 1000
        text = vmfpy.synthesize_entities(
            [
                {
                    "classname": "info_null",
                    "targetname": "mp_0_2",
                    "pos": (1, 2, 66),
                    "visgroup": vmfpy.VISGROUP_MARKERS,
                },
                {
                    "classname": "info_teleport_destination",
                    "targetname": "warp_yard",
                    "pos": (3, -100, 4),
                    "ang": (0, 90, 0),
                    "visgroup": vmfpy.VISGROUP_MARKERS,
                },
                {
                    "classname": "prop_static",
                    "targetname": "post_1_0",
                    "pos": (0, -100, 4),
                    "ang": (0, 0, 0),
                    "mdl": "models/trakpak3_us/signs/milepost.mdl",
                    "visgroup": vmfpy.VISGROUP_MARKERS,
                },
            ]
        )
        self.assertEqual(text.count('"classname" "prop_static"'), 1)
        self.assertIn('"classname" "info_null"', text)
        self.assertIn('"targetname" "mp_0_2"', text)
        self.assertIn('"origin" "1 2 66"', text)
        self.assertIn('"classname" "info_teleport_destination"', text)
        self.assertIn('"angles" "0 90 0"', text)
        self.assertIn('"targetname" "warp_yard"', text)
        self.assertIn('"targetname" "post_1_0"', text)
        self.assertIn('"visgroupid" "30"', text)
        self.assertIn("models/trakpak3_us/signs/milepost.mdl", text)


def _install(names, extra=None):

    manifest = load_manifest()
    track.track_model_library.clear()
    track.valid_tracks_cache.clear()
    for name in names:
        track.track_model_library[name] = manifest["models"][name]["routes"][0]
    if extra:
        track.track_model_library.update(extra)


def _search(profile, border, seed=0):

    random.seed(seed)
    track.valid_tracks_cache.clear()
    trackhammer.clear_occupied()
    trackhammer.set_border_override(border)
    buf = io.StringIO()
    with redirect_stdout(buf):
        steps = trackhammer.generation_process(START, profile, 5000, 8)
    return steps or [], buf.getvalue()


class OverrideTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):

        lines.Beziers = []
        cfg.CFG["run_length_tolerance"] = 100
        cfg.CFG["trackhammer_fit_run_length"] = 1
        cfg.CFG["trackhammer_attempt_limit"] = 20000
        trackhammer.initialize()
        _install((FLAT, GRADED, CURVE), {DOWN: _piece(512, grade=-1)})

    def tearDown(self):

        trackhammer.set_border_override(None)

    def test_flat_and_straight_only_filter_candidates(self):

        flat = {"min_radius": 0, "min_grade": 0, "max_grade": 0}
        self.assertEqual(
            set(track.valid_next_tracks("0fw", {"flat": True, "min_radius": 0})),
            set(track.valid_next_tracks("0fw", flat)),
        )
        both = set(track.valid_next_tracks("0fw", flat))
        self.assertIn(FLAT, both)
        self.assertIn(CURVE, both)
        self.assertNotIn(GRADED, both)
        self.assertNotIn(DOWN, both)

        straight = set(
            track.valid_next_tracks(
                "0fw",
                {"min_radius": 2, "straight_only": True, "flat": True},
            )
        )
        self.assertEqual(straight, {FLAT})
        forced = set(
            track.valid_next_tracks(
                "0fw",
                {"min_radius": 0, "force_straight": True, "min_grade": 0, "max_grade": 0},
            )
        )
        self.assertEqual(forced, {FLAT})

        graded = set(
            track.valid_next_tracks(
                "0fw", {"min_radius": 0, "min_grade": 1, "max_grade": 1}
            )
        )
        self.assertEqual(graded, {GRADED})

        # A straight-only result must not stick in the cache.
        track.valid_tracks_cache.clear()
        self.assertEqual(
            set(track.valid_next_tracks("0fw", {"straight_only": True, "flat": True})),
            {FLAT},
        )
        opened = set(track.valid_next_tracks("0fw", {"min_radius": 0}))
        self.assertIn(CURVE, opened)
        self.assertIn(GRADED, opened)
        self.assertIn(DOWN, opened)

    def _models_and_zones(self, steps):

        models = []
        zones = []
        for step in steps:
            if step.get("switch_zone"):
                zones.append(step["switch_zone"])
            model = step.get("model") or ""
            if model:
                models.append(model)
        return models, zones

    def test_straight_flat_run_gives_way_to_a_grade(self):

        profile = [
            [(0, 0), 1536, {"min_radius": 0, "straight_only": True, "flat": True}],
            [(0, 0), 3072, {"min_radius": 0, "min_grade": 1, "max_grade": 1}],
        ]

        def wide(point):
            return abs(point[0]) < 100000 and abs(point[1]) < 20000

        steps, log = _search(profile, wide)
        self.assertNotIn("Went over a boundary", log)
        self.assertEqual(trackhammer.search_stats["died"], 0, log[-400:])
        models, zones = self._models_and_zones(steps)
        self.assertEqual(zones, [])
        self.assertEqual(models[:3], [FLAT, FLAT, FLAT])
        self.assertEqual(models[3:], [GRADED, GRADED, GRADED])
        self.assertNotIn(CURVE, models)

    def test_straight_only_still_builds_the_following_siding(self):

        profile = [
            [(0, 0), 1536, {"min_radius": 0, "force_straight": True, "flat": True}],
            [(0, 1), 3072, {"min_radius": 0, "min_grade": 0, "max_grade": 0}],
        ]

        def wide(point):
            return abs(point[0]) < 100000 and abs(point[1]) < 20000

        steps, log = _search(profile, wide)
        self.assertNotIn("Went over a boundary", log)
        self.assertEqual(trackhammer.search_stats["died"], 0, log[-400:])
        models, zones = self._models_and_zones(steps)
        self.assertEqual(zones, [((0, 0), (0, 1))])
        self.assertTrue(models)
        self.assertTrue(all(model == FLAT for model in models))
        self.assertNotIn(CURVE, models)

    def test_force_straight_rejects_a_long_straight_and_keeps_going(self):

        _install((FLAT, LONG, CURVE))
        seen = []
        original = trackhammer.generate_selection_of_possible_tracks

        def ordered(node, count, current_run={}):
            options = original(node, count, current_run)
            seen.append(list(options))
            # pop() tries the tail first, so the long straight is rejected
            # before the short one is placed.
            rest = [model for model in options if model != LONG]
            if LONG in options:
                rest.append(LONG)
            return rest

        trackhammer.generate_selection_of_possible_tracks = ordered
        try:
            profile = [
                [(0, 0), 1536, {"min_radius": 0, "force_straight": True, "flat": True}],
            ]

            def tight(point):
                return -3000 < point[0] < 5000 and abs(point[1]) < 400

            steps, log = _search(profile, tight)
        finally:
            trackhammer.generate_selection_of_possible_tracks = original

        self.assertEqual(trackhammer.search_stats["died"], 0, log[-400:])
        self.assertGreater(trackhammer.search_stats["rejected"], 0)
        models = [step["model"] for step in steps if step.get("model")]
        self.assertEqual(models, [FLAT, FLAT, FLAT])
        self.assertTrue(seen)
        self.assertTrue(all(CURVE not in batch for batch in seen))
        self.assertTrue(all(LONG in batch for batch in seen))


if __name__ == "__main__":
    unittest.main()
