"""Run length is plain track between ladders, and a ladder that cannot
be built rejects the move.

Pieces are real TrakPak3 straights and one real 90° arc from the manifest.
The switch geometry is the real condensed siding, so a 6-track add on 0fw
is the 9216-unit ladder.
"""

import io
import math
import os
import random
import sys
import time
import types
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, track, trackhammer
from railmancer.switches import zone_length
from railmancer.trakpak_manifest import load_manifest

STRAIGHTS = (
    "models/trakpak3_rsg/straights/s0512_0fw_0pg_+0512x00000x0000.mdl",
    "models/trakpak3_rsg/straights/s1024_0fw_0pg_+1024x00000x0000.mdl",
    "models/trakpak3_rsg/straights/s2048_0fw_0pg_+2048x00000x0000.mdl",
    "models/trakpak3_rsg/straights/s4096_0fw_0pg_+4096x00000x0000.mdl",
)
LONG_STRAIGHT = "models/trakpak3_rsg/straights/s8192_0fw_0pg_+8192x00000x0000.mdl"
WIDE_CURVE = "models/trakpak3_rsg/arcs/r6144/a0fw_8lt_left_0pg_+6144x-6144x0000.mdl"
PARAMS = {"min_radius": 0, "min_grade": 0, "max_grade": 0}
# Plain lengths: 5000, then a short 2500 on the wide run, then 4200.
# The 0→6 ladder is 9216, longer than that short run.
PROFILE = [
    [(0, 0), 5000, PARAMS],
    [(0, 6), 7500, PARAMS],
    [(0, 0), 11700, PARAMS],
]
RUN_LENGTHS = (5000, 2500, 4200)
START = ((0.0, 0.0, 0.0), "0fw", 0, False)


def _install(names):

    manifest = load_manifest()
    track.track_model_library.clear()
    track.valid_tracks_cache.clear()
    for name in names:
        track.track_model_library[name] = manifest["models"][name]["routes"][0]


def _open_map(point):

    return -120000 < point[0] < 5000 and abs(point[1]) < 8000


def _centerline_lane(point):

    # Wide enough for the mainline, not for track 6 (6 * 192 = 1152).
    return -120000 < point[0] < 5000 and abs(point[1]) < 400


def _plain_segments(steps):

    segments = []
    acc = 0.0
    for step in steps:
        model = step.get("model") or ""
        if model:
            acc += float(track.get_length(model))
        if step.get("switch_zone"):
            segments.append(acc)
            acc = 0.0
    segments.append(acc)
    return segments


def _search(profile, seed, border, limit=20000, prepare=None):

    random.seed(seed)
    track.valid_tracks_cache.clear()
    trackhammer.clear_occupied()
    trackhammer.set_border_override(border)
    cfg.CFG["trackhammer_attempt_limit"] = limit
    if prepare:
        prepare()
    buf = io.StringIO()
    with redirect_stdout(buf):
        steps = trackhammer.generation_process(START, profile, 5000, 8)
    return steps or [], buf.getvalue()


class RunLengthTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))
        cls.manifest_zone = zone_length((0, 0), (0, 6), "0fw")

    def setUp(self):

        trackhammer.initialize()
        _install(STRAIGHTS)
        cfg.CFG["run_length_tolerance"] = 1000
        cfg.CFG["trackhammer_fit_run_length"] = 1
        cfg.CFG["trackhammer_attempt_limit"] = 20000

    def test_config_default_is_one_thousand(self):

        self.assertEqual(cfg.get("run_length_tolerance"), 1000)
        self.assertEqual(cfg.get("trackhammer_fit_run_length"), 1)
        # The 6-track add the owner measured: 6 * 1536 on 0fw.
        self.assertEqual(self.manifest_zone, 9216)

    def test_many_seeds_land_in_tolerance_and_keep_every_ladder(self):

        tol = cfg.get("run_length_tolerance")
        for seed in range(16):
            steps, log = _search(PROFILE, seed, _open_map)
            with self.subTest(seed=seed):
                self.assertNotIn("Went over a boundary", log, log[-500:])
                self.assertEqual(trackhammer.search_stats["died"], 0, log[-500:])
                self.assertEqual(trackhammer.search_stats["stuck"], 0, log[-500:])
                zones = [step["switch_zone"] for step in steps if step.get("switch_zone")]
                self.assertEqual(zones, [((0, 0), (0, 6)), ((0, 6), (0, 0))])
                seen = 0
                for step in steps:
                    if step.get("switch_zone"):
                        seen += 1
                    self.assertEqual(step["current_run_id"], seen)
                segments = _plain_segments(steps)
                self.assertEqual(len(segments), 3)
                for segment, target in zip(segments, RUN_LENGTHS):
                    self.assertLessEqual(abs(segment - target), tol)
                # The short run is plain track only. A 9216 ladder does not fit in it.
                self.assertLess(segments[1], 4000)
                self.assertGreater(segments[1], 0)

    def test_ladder_off_the_map_rejects_and_drops_no_siding(self):

        started = time.perf_counter()
        steps, log = _search(PROFILE[:2], 1, _centerline_lane, limit=5000)
        self.assertLess(time.perf_counter() - started, 5.0, log[-400:])
        self.assertEqual(trackhammer.search_stats["died"], 1)
        self.assertGreater(trackhammer.search_stats["rejected"], 0)
        self.assertFalse(any(step.get("switch_zone") for step in steps))
        self.assertTrue(all(step["current_run_id"] == 0 for step in steps))
        # Kept prefix stops before the window. Entering it without a ladder
        # would be the old "drop the siding and cross the boundary" bug.
        placed = sum(_plain_segments(steps))
        self.assertGreater(placed, 0)
        self.assertLess(placed, 5000 - 1000)
        self.assertNotIn("Went over a boundary", log)

    def test_ladder_blocked_rejects_and_drops_no_siding(self):

        def block_outer_track():

            # Cells the centerline (y=0) does not use when blocks are 400 wide.
            trackhammer.BlockHorizontal = 400
            for cx in range(-80, 10):
                for cy in (2, 3, 4):
                    trackhammer.HeightTable[(cx, cy)] = 0.0

        started = time.perf_counter()
        steps, log = _search(
            PROFILE[:2], 2, _open_map, limit=5000, prepare=block_outer_track
        )
        self.assertLess(time.perf_counter() - started, 5.0, log[-400:])
        self.assertEqual(trackhammer.search_stats["died"], 1)
        self.assertGreater(trackhammer.search_stats["rejected"], 0)
        self.assertFalse(any(step.get("switch_zone") for step in steps))
        self.assertTrue(all(step["current_run_id"] == 0 for step in steps))
        placed = sum(_plain_segments(steps))
        self.assertGreater(placed, 0)
        self.assertLess(placed, 5000 - 1000)
        self.assertNotIn("Went over a boundary", log)

    def test_overshoot_is_a_dead_end(self):

        _install((LONG_STRAIGHT,))
        profile = [
            [(0, 0), 3000, PARAMS],
            [(0, 6), 6000, PARAMS],
        ]
        started = time.perf_counter()
        steps, log = _search(profile, 0, _open_map, limit=1000)
        self.assertLess(time.perf_counter() - started, 2.0)
        self.assertEqual(steps, [])
        self.assertEqual(trackhammer.search_stats["died"], 1)
        self.assertNotIn("Went over a boundary", log)

    def test_fit_disabled_still_places_track_and_no_ladder(self):

        # The old switch is still there. Off means "do not fit runs".
        cfg.CFG["trackhammer_fit_run_length"] = 0
        profile = [[(0, 0), 3000, PARAMS]]
        steps, _log = _search(profile, 0, _open_map)
        self.assertGreaterEqual(steps[-1]["length"], 3000)
        self.assertFalse(any(step.get("switch_zone") for step in steps))


class StraightKillswitchTests(unittest.TestCase):

    def test_under_32_returns_without_hanging(self):

        track.straight_decomposition_cache.pop(16, None)
        track.straight_decomposition_cache.pop(0, None)
        started = time.perf_counter()
        with redirect_stdout(io.StringIO()) as buf:
            missing = track.decompose_length_to_straights(16)
            nothing = track.decompose_length_to_straights(0)
            still = track.decompose_length_to_straights(80)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0)
        self.assertEqual(missing, [])
        self.assertEqual(nothing, [])
        self.assertIn("Invalid decomposition length: 16", buf.getvalue())
        self.assertEqual(sum(still), 80)
        # A real straight length still decomposes, and does not spin.
        self.assertEqual(sum(track.decompose_length_to_straights(32)), 32)


class BoundsCheckTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):

        trackhammer.initialize()
        trackhammer.clear_occupied()

    def test_outer_track_catches_what_the_centerline_misses(self):

        _install(STRAIGHTS[:1])
        model = STRAIGHTS[0]
        start = START
        end = track.get_new_node_from_node_and_model(model, start, False, 0, 0)
        trackhammer.set_border_override(_centerline_lane)
        center = trackhammer.get_block_points_from_nodes(start, end)
        wide = trackhammer.get_block_points_from_nodes(start, end, (0, 6))
        self.assertTrue(all(abs(float(point[1])) < 400 for point in center))
        self.assertTrue(any(abs(float(point[1])) > 1000 for point in wide))
        self.assertIsNone(trackhammer.iterate_backbone(model, start, (0, 6)))
        placed = trackhammer.iterate_backbone(model, start, (0, 0))
        self.assertIsNotNone(placed)

    def test_curve_samples_the_bulge_the_chord_misses(self):

        _install((WIDE_CURVE,))
        model = WIDE_CURVE
        start = START
        end = track.get_new_node_from_node_and_model(model, start, False, 0, 0)
        # Block size larger than the chord, so the old walk sampled only the end.
        trackhammer.BlockHorizontal = 20000
        points = trackhammer.get_block_points_from_nodes(start, end)
        radius = 6144.0
        bulge = (-radius * math.sqrt(2) / 2.0, -radius * (1.0 - math.sqrt(2) / 2.0))
        nearest = min(
            math.hypot(float(point[0]) - bulge[0], float(point[1]) - bulge[1])
            for point in points
        )
        self.assertLess(nearest, 32.0)
        chord_end = math.hypot(float(end[0][0]) - bulge[0], float(end[0][1]) - bulge[1])
        self.assertGreater(chord_end, 1500.0)

        def near_chord(point):

            sx, sy = 0.0, 0.0
            ex, ey = float(end[0][0]), float(end[0][1])
            vx, vy = ex - sx, ey - sy
            length2 = vx * vx + vy * vy
            t = ((point[0] - sx) * vx + (point[1] - sy) * vy) / length2
            t = max(0.0, min(1.0, t))
            return math.hypot(point[0] - t * vx, point[1] - t * vy) <= 400.0

        trackhammer.set_border_override(near_chord)
        self.assertTrue(near_chord((int(end[0][0]), int(end[0][1]))))
        self.assertIsNone(trackhammer.iterate_backbone(model, start, (0, 0)))
        trackhammer.set_border_override(lambda point: True)
        self.assertIsNotNone(trackhammer.iterate_backbone(model, start, (0, 0)))


if __name__ == "__main__":
    unittest.main()
