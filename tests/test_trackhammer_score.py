import math
import random
import unittest

from railmancer import cfg, tools, track, trackhammer
from railmancer.benchmark_trackhammer import (
    curve_move,
    l_border,
    rectangle_border,
    register_piece,
    straight_move,
)


def layers_for(z, block_vertical):

    fz = z / block_vertical
    bz = math.floor(fz)
    if fz - bz > 0.5:
        return {bz, bz + 1}
    return {bz - 1, bz}


class TrackhammerScoreTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize("railmancer/config.json")
        cfg.CFG["trackhammer_scored_selection"] = 0
        cfg.CFG["trackhammer_attempt_limit"] = 4000
        trackhammer.initialize()

    def setUp(self):

        track.track_model_library.clear()
        track.valid_tracks_cache.clear()
        cfg.CFG["trackhammer_scored_selection"] = 0
        cfg.CFG["trackhammer_attempt_limit"] = 4000
        cfg.CFG["trackhammer_score_weight_jitter"] = 0
        cfg.CFG["trackhammer_border"] = 30000
        trackhammer.BlockHorizontal = 1000
        trackhammer.BlockVertical = 1000
        trackhammer.Block_Standoff_Distance = 3000
        trackhammer.set_border_override(None)
        trackhammer.rebuild_border_distance()
        trackhammer.clear_occupied()
        trackhammer.debug_overall_count = 0
        trackhammer.logLength = 0

    def _add(self, name, start, end, radius, move, length, grade):

        register_piece(name, start, end, radius, length, move, grade)

    def test_vertical_clearance_is_two_block_layers(self):

        block_vertical = 1260
        trackhammer.BlockVertical = block_vertical
        self.assertEqual(trackhammer.vertical_clearance(), 2 * block_vertical)

        low = 630.1
        high = low + 2 * block_vertical
        self.assertTrue(layers_for(low, block_vertical).isdisjoint(layers_for(high, block_vertical)))
        self.assertFalse(
            layers_for(low, block_vertical).isdisjoint(
                layers_for(high - 0.2, block_vertical)
            )
        )

    def test_height_map_add_remove_recomputes_column_top(self):

        low_ids = trackhammer.blocks_new([[0, 0, 100], [0, 0, 400]])
        self.assertEqual(trackhammer.HeightMap[(0, 0)], 400.0)
        self.assertEqual(
            trackhammer.HeightCounts[(0, 0)],
            len(trackhammer.HeightColumns[(0, 0)]),
        )
        self.assertIs(trackhammer.Blocks[low_ids[0]], True)

        # 2500 is a different z-layer pair than 100/400, so it can reserve
        # new blocks in the same 2D column.
        low_count = trackhammer.HeightCounts[(0, 0)]
        high_ids = trackhammer.blocks_new([[0, 0, 2500]])
        self.assertTrue(high_ids)
        self.assertEqual(trackhammer.HeightMap[(0, 0)], 2500.0)
        self.assertGreater(trackhammer.HeightCounts[(0, 0)], low_count)
        self.assertEqual(
            trackhammer.HeightCounts[(0, 0)],
            len(trackhammer.HeightColumns[(0, 0)]),
        )

        trackhammer.blocks_remove(high_ids)
        self.assertEqual(trackhammer.HeightMap[(0, 0)], 400.0)
        self.assertEqual(
            trackhammer.HeightCounts[(0, 0)],
            len(trackhammer.HeightColumns[(0, 0)]),
        )

        trackhammer.blocks_remove(low_ids)
        self.assertNotIn((0, 0), trackhammer.HeightMap)
        self.assertNotIn((0, 0), trackhammer.HeightCounts)
        self.assertNotIn((0, 0), trackhammer.HeightColumns)

    def test_height_map_does_not_raise_a_block_owned_earlier(self):

        trackhammer.blocks_new([[0, 0, 100]])
        trackhammer.blocks_new([[0, 0, 400]])
        self.assertEqual(trackhammer.HeightMap[(0, 0)], 100.0)

    def test_probe_reports_runway_and_occupied_top(self):

        cfg.CFG["trackhammer_score_probe_cells"] = 6
        trackhammer.blocks_new([[-5000, 0, 800]])
        probe = trackhammer.probe_from_node(([0, 0, 0], "0fw", 0, False))
        self.assertEqual(probe["hit_z"], 800.0)
        self.assertEqual(probe["hit_distance"], 5000)
        self.assertEqual(probe["clear_cells"], 4)
        self.assertEqual(probe["hugs"], 0)

    def test_probe_hugs_border_and_lower_layer(self):

        cfg.CFG["trackhammer_score_probe_cells"] = 3
        trackhammer.set_border_override(
            lambda point: abs(point[0]) < 20000 and abs(point[1]) < 400
        )
        trackhammer.rebuild_border_distance()
        border_probe = trackhammer.probe_from_node(([0, 0, 0], "0fw", 0, False))
        self.assertEqual(border_probe["hugs"], 2)

        trackhammer.set_border_override(None)
        cfg.CFG["trackhammer_border"] = 30000
        trackhammer.rebuild_border_distance()
        trackhammer.clear_occupied()
        trackhammer.blocks_new([[0, 1000, 100]])
        lower = trackhammer.probe_from_node(([0, 0, 5000], "0fw", 0, False))
        self.assertEqual(lower["hugs"], 1)

    def test_border_distance_rectangle_and_l(self):

        trackhammer.BlockHorizontal = 1000
        cfg.CFG["trackhammer_border"] = 20000
        trackhammer.set_border_override(rectangle_border(5000, 3000))
        trackhammer.rebuild_border_distance()
        self.assertIn((0, 0), trackhammer.BorderDistance)
        self.assertGreater(
            trackhammer.BorderDistance[(0, 0)],
            trackhammer.BorderDistance[(4, 0)],
        )
        self.assertNotIn((6, 0), trackhammer.BorderDistance)

        trackhammer.set_border_override(l_border(8000, 2000))
        trackhammer.rebuild_border_distance()
        # Bottom arm of the L.
        self.assertIn((0, -4), trackhammer.BorderDistance)
        # Missing top-right quadrant.
        self.assertNotIn((5, 5), trackhammer.BorderDistance)

    def test_scoring_rejects_a_grade_that_cannot_clear(self):

        trackhammer.BlockVertical = 1000
        cfg.CFG["trackhammer_score_weight_grade"] = 100
        cfg.CFG["trackhammer_score_weight_runway"] = 2
        cfg.CFG["trackhammer_score_weight_hug"] = 0
        cfg.CFG["trackhammer_score_weight_heading"] = 0
        cfg.CFG["trackhammer_score_weight_reverse"] = 4
        cfg.CFG["trackhammer_score_weight_jitter"] = 0
        blocked = {
            "clear_cells": 2,
            "probe_cells": 5,
            "hit_z": 1000,
            "hit_distance": 5000,
            "hugs": 0,
        }
        # H = 2000, required = (1000 + 2000 - 0) / 5000 = 0.6
        self.assertAlmostEqual(trackhammer.required_grade(blocked, 0), 0.6)
        self.assertIsNone(
            trackhammer.placement_cost(0.0, blocked, 0, {"min_grade": 0}, 0, 0, 0)
        )
        just = trackhammer.placement_cost(0.6, blocked, 0, {"min_grade": 0}, 0, 0, 0)
        steeper = trackhammer.placement_cost(
            0.7, blocked, 0, {"min_grade": 0}, 0, 0, 0
        )
        self.assertIsNotNone(just)
        self.assertGreater(steeper, just)

        open_probe = {
            "clear_cells": 5,
            "probe_cells": 5,
            "hit_z": None,
            "hit_distance": None,
            "hugs": 0,
        }
        flat = trackhammer.placement_cost(0.0, open_probe, 0, {"min_grade": 0}, 0, 0, 0)
        climbing = trackhammer.placement_cost(
            0.03, open_probe, 0, {"min_grade": 0}, 0, 0, 0
        )
        self.assertLess(flat, climbing)

        flipped = trackhammer.placement_cost(
            0.0, open_probe, 0, {"min_grade": 0}, 0, -1, 1
        )
        self.assertAlmostEqual(flipped, 4.0)

    def test_top_k_keeps_the_shallowest_grades(self):

        cfg.CFG["trackhammer_scored_selection"] = 1
        cfg.CFG["trackhammer_score_top_k"] = 2
        cfg.CFG["trackhammer_score_probe_cells"] = 4
        cfg.CFG["trackhammer_score_weight_grade"] = 100
        cfg.CFG["trackhammer_score_weight_runway"] = 0
        cfg.CFG["trackhammer_score_weight_hug"] = 0
        cfg.CFG["trackhammer_score_weight_heading"] = 0
        cfg.CFG["trackhammer_score_weight_reverse"] = 0
        cfg.CFG["trackhammer_score_weight_jitter"] = 0
        for grade in (0.0, 1.2, 3.2):
            move, length = straight_move("0fw", 1024, grade)
            self._add(f"g{grade}", "0fw", "0fw", 0, move, length, grade)

        chosen = trackhammer.select_scored_candidates(
            ([0, 0, 0], "0fw", 0, False),
            {"min_radius": 0, "min_grade": 0, "max_grade": 3},
            0,
            (0, 0),
            0,
            0,
            [[(0, 0), 10**9, {}]],
        )
        self.assertEqual(chosen, ["g0.0", "g1.2"])

    def test_failed_state_memo_skips_a_known_dead_end(self):

        move, length = straight_move("0fw", 1024, 0)
        self._add("flat", "0fw", "0fw", 0, move, length, 0)
        node = ([0, 0, 0], "0fw", 0, False)
        params = {"min_radius": 0, "min_grade": 0, "max_grade": 0}
        profile = [[(0, 0), 10**9, params]]
        first = trackhammer.select_scored_candidates(
            node, params, 0, (0, 0), 0, 0, profile
        )
        self.assertEqual(first, ["flat"])
        placed = trackhammer.iterate_backbone("flat", node, (0, 0))
        trackhammer.FailedStates.add(trackhammer.state_key(placed[0], 0))
        before = trackhammer.search_stats["memo_skips"]
        second = trackhammer.select_scored_candidates(
            node, params, 0, (0, 0), 0, 0, profile
        )
        self.assertEqual(second, [])
        self.assertGreater(trackhammer.search_stats["memo_skips"], before)

    def test_top_k_exhaustion_pops_one_and_takes_the_next_best(self):

        self._install_wall_pair()
        cfg.CFG["trackhammer_scored_selection"] = 1
        cfg.CFG["trackhammer_score_top_k"] = 3
        cfg.CFG["trackhammer_score_pop_limit"] = 10
        cfg.CFG["trackhammer_score_probe_cells"] = 2
        self._zero_weights_except_heading()
        trackhammer.set_border_override(
            lambda point: -5000 < point[0] < 8000 and abs(point[1]) < 8000
        )
        trackhammer.rebuild_border_distance()

        steps = self._run([0, 0, 0], 4500 / 63360.0)
        self.assertGreaterEqual(trackhammer.search_stats["one_step_pops"], 1)
        self.assertEqual(trackhammer.search_stats["distance_backtracks"], 0)
        self.assertEqual(trackhammer.search_stats["died"], 0)
        self.assertEqual(trackhammer.search_stats["stuck"], 0)
        self.assertTrue(any(int(step["node"][2]) == -90 for step in steps))
        self.assertGreaterEqual(steps[-1]["length"], 4500)

    def test_pop_limit_falls_back_to_distance_backtrack(self):

        self._install_wall_pair()
        cfg.CFG["trackhammer_scored_selection"] = 1
        cfg.CFG["trackhammer_score_top_k"] = 3
        cfg.CFG["trackhammer_score_pop_limit"] = 0
        cfg.CFG["trackhammer_score_probe_cells"] = 2
        self._zero_weights_except_heading()
        trackhammer.set_border_override(
            lambda point: -5000 < point[0] < 8000 and abs(point[1]) < 8000
        )
        trackhammer.rebuild_border_distance()

        steps = self._run([0, 0, 0], 4500 / 63360.0)
        self.assertGreaterEqual(trackhammer.search_stats["distance_backtracks"], 1)
        self.assertEqual(trackhammer.search_stats["one_step_pops"], 0)
        self.assertEqual(trackhammer.search_stats["died"], 0)
        self.assertGreaterEqual(steps[-1]["length"], 4500)

    def test_empty_sprinkle_returns_nothing(self):

        self.assertEqual(tools.sprinkle_selector([], 5), [])
        self.assertEqual(tools.sprinkle_selector(["a"], 0), [])

    def test_scored_mode_off_still_sprinkles_and_matches_itself(self):

        for grade in (0.0, 1.2):
            for direction in ("0fw", "1rt", "1lt"):
                move, length = straight_move(direction, 1024, grade)
                self._add(
                    f"{direction}-{grade}",
                    direction,
                    direction,
                    0,
                    move,
                    length,
                    grade,
                )
        move, arc = curve_move("0fw", "1rt", 4096, 0)
        self._add("curve", "0fw", "1rt", 4096, move, arc, 0)

        sprinkled = []
        scored = []
        real_sprinkle = tools.sprinkle_selector
        real_select = trackhammer.select_scored_candidates

        def watch_sprinkle(choices, count):
            sprinkled.append(count)
            return real_sprinkle(choices, count)

        def watch_select(*args, **kwargs):
            scored.append(1)
            return real_select(*args, **kwargs)

        tools.sprinkle_selector = watch_sprinkle
        trackhammer.select_scored_candidates = watch_select
        try:
            cfg.CFG["trackhammer_scored_selection"] = 0
            random.seed(7)
            first = self._run([0, 0, 0], 0.04)
            self._reset_between_runs()
            random.seed(7)
            second = self._run([0, 0, 0], 0.04)
        finally:
            tools.sprinkle_selector = real_sprinkle
            trackhammer.select_scored_candidates = real_select

        self.assertTrue(sprinkled)
        self.assertEqual(scored, [])
        self.assertEqual(
            [step["model"] for step in first],
            [step["model"] for step in second],
        )
        self.assertEqual(first[-1]["length"], second[-1]["length"])

    def _zero_weights_except_heading(self):

        cfg.CFG["trackhammer_score_weight_grade"] = 0
        cfg.CFG["trackhammer_score_weight_runway"] = 0
        cfg.CFG["trackhammer_score_weight_hug"] = 0
        cfg.CFG["trackhammer_score_weight_heading"] = 2
        cfg.CFG["trackhammer_score_weight_reverse"] = 0
        cfg.CFG["trackhammer_score_weight_jitter"] = 0

    def _install_wall_pair(self):

        move, length = straight_move("0fw", 2000, 0)
        self._add("straight", "0fw", "0fw", 0, move, length, 0)
        move, arc = curve_move("0fw", "8rt", 2048, 0)
        self._add("turn", "0fw", "8rt", 2048, move, arc, 0)

    def _reset_between_runs(self):

        trackhammer.clear_occupied()
        trackhammer.debug_overall_count = 0
        trackhammer.logLength = 0
        track.valid_tracks_cache.clear()

    def _run(self, origin, miles):

        self._reset_between_runs()
        profile = trackhammer.aggregate_track_profile(
            [
                [
                    (0, 0),
                    miles,
                    {"min_radius": 0, "min_grade": 0, "max_grade": 0},
                ]
            ]
        )
        return trackhammer.create_rail_path([origin, "0fw", 0, False], profile)


if __name__ == "__main__":
    unittest.main()
