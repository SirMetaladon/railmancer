"""Notepad routes become Trackhammer mainline lists.

Weights share whatever target_miles is left after fixed segments and
switch ladders. The pasteable list is the same (tracks, miles, params)
shape generate_mainline already aggregates.
"""

import ast
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from railmancer import tools
from railmancer.route_builder import RouteError, build, main, parse, solve
from railmancer.switches import zone_length
from railmancer.trackhammer import aggregate_track_profile


def _route(text, no_merge=False):
    route, rendered = build(text, no_merge=no_merge)
    return route, rendered


def _mainline(rendered):
    rhs = rendered.split("Mainline = ", 1)[1]
    if "\nWarps = " in rhs:
        rhs = rhs.split("\nWarps = ", 1)[0]
    cleaned = "\n".join(line.split("#", 1)[0] for line in rhs.splitlines())
    return ast.literal_eval(cleaned)


def _exec_block(rendered):
    start = rendered.split("Paste into railmancer.py", 1)[1]
    start = start.split("------------------------", 1)[1]
    namespace = {}
    exec(start, namespace)
    return namespace


class ParseTests(unittest.TestCase):
    def test_comments_tracks_params_and_lengths(self):
        route, _rendered = _route(
            """
            # Vancouver approach
            target_miles = 10
            siding_miles = 0.6
            siding_side = right
            ladder_allowance = 0
            start_milepost = 4
            min_radius = 2
            min_grade = 1
            max_grade = 2

            # MP19 to MP20: Brunswick Siding
            # east end is the crossing
            siding straight

            # a flexible milepost span
            8 miles 1 track max_radius=4

            # explicit pairs and a grade band
            (1, 1) weight=3 min_grade=0 max_grade=1

            # two on the right, fixed
            (0, 2) fixed=0.4 flat

            # double is one extra track on the right
            double 2 miles

            # three tracks total, main plus two right
            3 track 1 mile min=0.2 max=2

            # left-hand count written out
            (2, 1) 4 mi join=stub
            """
        )
        siding, flex, pair, yard, doubled, three, left = route.segments
        self.assertEqual(siding.comments[0], "MP19 to MP20: Brunswick Siding")
        self.assertEqual(siding.comments[1], "east end is the crossing")
        self.assertEqual(siding.tracks, (0, 1))
        self.assertEqual(siding.fixed, 0.6)
        self.assertEqual(siding.mode, "fixed")
        self.assertEqual(siding.params["straight_only"], True)
        self.assertEqual(siding.params["min_radius"], 2)
        self.assertNotIn("max_radius", siding.params)
        self.assertEqual(siding.params["min_grade"], 1)

        self.assertEqual(flex.tracks, (0, 0))
        self.assertEqual(flex.weight, 8)
        self.assertEqual(flex.params["max_radius"], 4)
        self.assertAlmostEqual(flex.miles + pair.miles + doubled.miles + three.miles + left.miles, 10 - 0.6 - 0.4)

        self.assertEqual(pair.tracks, (1, 1))
        self.assertEqual(pair.weight, 3)
        self.assertEqual(pair.params["min_grade"], 0)
        self.assertEqual(pair.params["max_grade"], 1)
        self.assertEqual(pair.params["min_radius"], 2)

        self.assertEqual(yard.tracks, (0, 2))
        self.assertEqual(yard.fixed, 0.4)
        self.assertEqual(yard.params["flat"], True)
        self.assertNotIn("min_grade", yard.params)
        self.assertNotIn("max_grade", yard.params)
        self.assertEqual(yard.params["min_radius"], 2)

        self.assertEqual(doubled.tracks, (0, 1))
        self.assertEqual(doubled.weight, 2)
        self.assertEqual(three.tracks, (0, 2))
        self.assertEqual(three.weight, 1)
        self.assertEqual(three.min_miles, 0.2)
        self.assertEqual(three.max_miles, 2)
        self.assertEqual(left.tracks, (2, 1))
        self.assertEqual(left.params["join"], "stub")
        self.assertEqual(route.start_milepost, 4)

    def test_siding_side_and_length_overrides(self):
        route, _rendered = _route(
            """
            target_miles = 5
            siding_miles = 0.6
            siding_side = left
            ladder_allowance = 0

            siding
            siding fixed=0.25
            siding weight=2
            """
        )
        bare, pinned, weighted = route.segments
        self.assertEqual(bare.tracks, (1, 0))
        self.assertEqual(bare.miles, 0.6)
        self.assertEqual(pinned.miles, 0.25)
        self.assertEqual(pinned.mode, "fixed")
        self.assertEqual(weighted.weight, 2)
        self.assertEqual(weighted.mode, "flex")
        self.assertAlmostEqual(weighted.miles, 5 - 0.6 - 0.25)

    def test_handbuilt_is_kept_out_of_the_run(self):
        route, rendered = _route(
            """
            target_miles = 2
            ladder_allowance = 0

            # north
            1 miles 1 track

            # Squamish yard, drawn by hand
            handbuilt 0.4 miles

            # south
            1 miles 1 track

            # remnant, not generated
            skip
            """
        )
        self.assertEqual(route.segments[1].mode, "handbuilt")
        self.assertEqual(route.segments[3].mode, "handbuilt")
        self.assertIsNone(route.segments[1].miles)
        self.assertAlmostEqual(route.segments[1].note_miles, 0.4)
        self.assertAlmostEqual(route.segments[0].miles, 1)
        self.assertAlmostEqual(route.segments[2].miles, 1)
        self.assertNotIn("Squamish yard", rendered.split("Mainline = ", 1)[1])
        self.assertIn("Squamish yard, drawn by hand", rendered)
        self.assertIn("not in the run", rendered)
        mainline = _mainline(rendered)
        self.assertEqual(len(mainline), 2)

    def test_handbuilt_cannot_carry_a_warp(self):
        with self.assertRaises(RouteError) as caught:
            parse(
                """
                target_miles = 1
                handbuilt warp=yard
                """
            )
        self.assertIn("warp", str(caught.exception))

    def test_unknown_parameter_and_late_setting(self):
        with self.assertRaises(RouteError) as caught:
            parse(
                """
                target_miles = 1
                1 miles 1 track minn_grade=1
                """
            )
        self.assertIn("minn_grade", str(caught.exception))
        self.assertIn("min_grade", str(caught.exception))
        with self.assertRaises(RouteError) as caught:
            parse(
                """
                1 miles 1 track
                target_miles = 1
                """
            )
        self.assertIn("settings go at the top", str(caught.exception))

    def test_fixed_and_weight_together_is_an_error(self):
        with self.assertRaises(RouteError) as caught:
            parse(
                """
                target_miles = 1
                fixed=0.2 8 miles 1 track
                """
            )
        self.assertIn("fixed", str(caught.exception).lower())

    def test_min_does_not_apply_to_a_fixed_length(self):
        with self.assertRaises(RouteError) as caught:
            parse(
                """
                target_miles = 1
                fixed=0.4 1 track min=0.2
                """
            )
        self.assertIn("flexible", str(caught.exception))


class SolverTests(unittest.TestCase):
    def test_weights_share_the_target(self):
        route, _rendered = _route(
            """
            target_miles = 8
            ladder_allowance = 0

            # A
            1 miles 1 track
            # B
            3 miles 1 track
            # C
            4 miles (1, 1)
            """
        )
        miles = [seg.miles for seg in route.segments]
        self.assertEqual(miles, [1, 3, 4])
        self.assertEqual([seg.mode for seg in route.segments], ["flex", "flex", "flex"])
        self.assertAlmostEqual(route.flex_total, 8)
        self.assertAlmostEqual(route.ladder_total, 0)
        self.assertAlmostEqual(route.fixed_total + route.flex_total + route.ladder_total, 8)

    def test_fixed_and_ladders_come_out_of_the_target(self):
        route, _rendered = _route(
            """
            target_miles = 2
            ladder_allowance_miles = 0.1

            # A
            1 miles (0, 0)
            # B
            fixed=0.5 (0, 1)
            # C
            1 miles (0, 0)
            """
        )
        self.assertAlmostEqual(route.ladder_total, 0.2)
        self.assertAlmostEqual(route.fixed_total, 0.5)
        self.assertEqual(route.segments[1].mode, "fixed")
        self.assertAlmostEqual(route.segments[0].miles, 0.65)
        self.assertAlmostEqual(route.segments[2].miles, 0.65)
        self.assertEqual(route.transitions[0]["steps"], 1)
        self.assertEqual(route.transitions[1]["steps"], 1)

    def test_both_sides_and_a_stub_change_the_step_count(self):
        route, _rendered = _route(
            """
            target_miles = 3
            ladder_allowance_miles = 0.1

            1 miles (0, 0)
            1 miles (1, 1)
            1 miles (1, 2) join_right=stub
            """
        )
        # (0, 0) -> (1, 1) is two steps. The next right-hand add is a stub.
        self.assertEqual(route.transitions[0]["steps"], 2)
        self.assertEqual(route.transitions[1]["steps"], 0)
        self.assertAlmostEqual(route.ladder_total, 0.2)
        self.assertEqual(route.segments[2].params["join"], {"left": "switch", "right": "stub"})
        self.assertAlmostEqual(sum(seg.miles for seg in route.segments), 2.8)

    def test_min_clamp_locks_and_the_rest_is_shared_again(self):
        route, _rendered = _route(
            """
            target_miles = 10
            ladder_allowance = 0

            # A
            1 miles 1 track min=6
            # B
            1 miles 1 track
            # C
            1 miles 1 track
            """
        )
        self.assertEqual(route.segments[0].mode, "clamped min")
        self.assertAlmostEqual(route.segments[0].miles, 6)
        self.assertAlmostEqual(route.segments[1].miles, 2)
        self.assertAlmostEqual(route.segments[2].miles, 2)

    def test_max_clamp_locks_and_the_rest_is_shared_again(self):
        route, _rendered = _route(
            """
            target_miles = 10
            ladder_allowance = 0

            # A
            1 miles 1 track max=2
            # B
            1 miles 1 track
            # C
            1 miles 1 track
            """
        )
        self.assertEqual(route.segments[0].mode, "clamped max")
        self.assertAlmostEqual(route.segments[0].miles, 2)
        self.assertAlmostEqual(route.segments[1].miles, 4)
        self.assertAlmostEqual(route.segments[2].miles, 4)

    def test_a_min_and_a_max_lock_one_at_a_time(self):
        route, _rendered = _route(
            """
            target_miles = 10
            ladder_allowance = 0

            # heavy, would take almost all of it, but cannot pass 9
            100 miles 1 track max=9
            # light, cannot shrink below 2
            1 miles 1 track min=2
            """
        )
        self.assertAlmostEqual(route.segments[1].miles, 2)
        self.assertEqual(route.segments[1].mode, "clamped min")
        self.assertAlmostEqual(route.segments[0].miles, 8)
        self.assertEqual(route.segments[0].mode, "flex")

    def test_default_min_and_default_max(self):
        route, _rendered = _route(
            """
            target_miles = 10
            ladder_allowance = 0
            default_min_miles = 0.5

            1 miles 1 track
            100 miles 1 track
            """
        )
        self.assertEqual(route.segments[0].mode, "clamped min")
        self.assertAlmostEqual(route.segments[0].miles, 0.5)
        self.assertAlmostEqual(route.segments[1].miles, 9.5)

        route, _rendered = _route(
            """
            target_miles = 10
            ladder_allowance = 0

            1 miles 1 track max=3
            1 miles 1 track max=3
            1 miles 1 track
            """
        )
        self.assertEqual([seg.mode for seg in route.segments], ["clamped max", "clamped max", "flex"])
        self.assertAlmostEqual(route.segments[0].miles, 3)
        self.assertAlmostEqual(route.segments[1].miles, 3)
        self.assertAlmostEqual(route.segments[2].miles, 4)

    def test_fixed_plus_ladders_over_the_target(self):
        with self.assertRaises(RouteError) as caught:
            _route(
                """
                target_miles = 1
                ladder_allowance_miles = 0.5
                fixed=1 (0, 0)
                1 miles (0, 1)
                """
            )
        message = str(caught.exception)
        self.assertIn("already over", message)
        self.assertIn("1.0000", message)
        self.assertIn("ladder", message.lower())

    def test_minimums_that_do_not_fit(self):
        with self.assertRaises(RouteError) as caught:
            _route(
                """
                target_miles = 3
                ladder_allowance = 0
                1 miles 1 track min=2
                1 miles 1 track min=2
                """
            )
        self.assertIn("minimums", str(caught.exception))

    def test_maximums_that_cannot_hold_the_budget(self):
        with self.assertRaises(RouteError) as caught:
            _route(
                """
                target_miles = 5
                ladder_allowance = 0
                1 miles 1 track max=2
                1 miles 1 track max=2
                """
            )
        self.assertIn("at most", str(caught.exception))

    def test_nothing_flexible_left_to_absorb_the_remainder(self):
        with self.assertRaises(RouteError) as caught:
            _route(
                """
                target_miles = 2
                ladder_allowance = 0
                fixed=1 1 track
                """
            )
        self.assertIn("no flexible", str(caught.exception))

    def test_default_ladder_step_is_one_switch_zone(self):
        route, _rendered = _route(
            """
            target_miles = 4
            direction = 0fw

            1 miles (0, 0)
            1 miles (0, 1)
            """
        )
        units = zone_length((0, 0), (0, 1), "0fw")
        self.assertEqual(units, 1536)
        self.assertAlmostEqual(route.ladder_step_units, 1536)
        self.assertAlmostEqual(route.per_step_miles, tools.miles(1536))
        self.assertAlmostEqual(route.per_step_miles, 1536 / (12 * 5280))
        self.assertEqual(route.transitions[0]["steps"], 1)
        self.assertAlmostEqual(route.ladder_total, tools.miles(1536))
        self.assertAlmostEqual(route.segments[0].miles + route.segments[1].miles, 4 - tools.miles(1536))

    def test_short_run_is_warned_in_the_preview(self):
        route, rendered = _route(
            """
            target_miles = 1
            ladder_allowance = 0

            # stub
            fixed=0.01 1 track
            # the rest
            1 miles 1 track
            """
        )
        self.assertTrue(route.segments[0].short)
        self.assertFalse(route.segments[1].short)
        self.assertLessEqual(tools.inches(0.01), 1000)
        self.assertIn("WARNING", rendered)
        self.assertIn("1000", rendered)
        self.assertIn("zero length", rendered)
        self.assertIn("0.0100 !", rendered)

    def test_warp_mile_is_the_segment_start_plus_the_milepost(self):
        route, rendered = _route(
            """
            target_miles = 2
            ladder_allowance = 0
            start_milepost = 3
            siding_miles = 0.6

            # approach
            1 miles 1 track
            # MP19 to MP20: Brunswick Siding
            siding warp=brunswick
            """
        )
        siding = route.segments[1]
        self.assertAlmostEqual(route.segments[0].miles, 1.4)
        self.assertAlmostEqual(siding.milepost_start, 4.4)
        self.assertAlmostEqual(siding.milepost_end, 5.0)
        namespace = _exec_block(rendered)
        self.assertEqual(namespace["Warps"][0]["name"], "brunswick")
        self.assertAlmostEqual(namespace["Warps"][0]["mile"], siding.milepost_start, places=5)


class MergeTests(unittest.TestCase):
    TEXT = """
        target_miles = 22
        ladder_allowance = 0
        merge = true

        # Alpha
        4 miles 1 track
        # Beta
        6 miles 1 track
        # Gamma
        straight 2 miles 1 track
        # Delta
        flat 2 miles 1 track
        # Epsilon
        3 miles (0, 1)
        # Zeta
        1 miles (0, 1)
        # yard note
        handbuilt
        # Theta
        4 miles (0, 1)
    """

    def test_merge_combines_only_matching_neighbors(self):
        route, rendered = _route(self.TEXT)
        mainline = _mainline(rendered)
        # Alpha+Beta, Gamma, Delta, Epsilon+Zeta, Theta. The yard blocks Theta.
        self.assertEqual(len(mainline), 5)
        self.assertEqual(mainline[0][0], (0, 0))
        self.assertAlmostEqual(mainline[0][1], 10)
        self.assertIn("Alpha + Beta", rendered)
        self.assertEqual(mainline[1][2]["straight_only"], True)
        self.assertAlmostEqual(mainline[1][1], 2)
        self.assertEqual(mainline[2][2]["flat"], True)
        self.assertNotIn("straight_only", mainline[2][2])
        self.assertEqual(mainline[3][0], (0, 1))
        self.assertAlmostEqual(mainline[3][1], 4)
        self.assertIn("Epsilon + Zeta", rendered)
        self.assertAlmostEqual(mainline[4][1], 4)
        self.assertIn("# Theta", rendered.split("Mainline = ", 1)[1])
        self.assertNotIn("Epsilon + Zeta + Theta", rendered)

    def test_no_merge_keeps_every_segment(self):
        _built, rendered = _route(self.TEXT, no_merge=True)
        mainline = _mainline(rendered)
        self.assertEqual(len(mainline), 7)
        self.assertNotIn("Alpha + Beta", rendered)
        self.assertIn("# Alpha", rendered)
        self.assertIn("# Beta", rendered)


class SnippetTests(unittest.TestCase):
    def test_snippet_is_python_and_matches_the_mainline_shape(self):
        _built, rendered = _route(
            """
            # header stays with the paste
            target_miles = 3
            ladder_allowance = 0
            min_radius = 2
            min_grade = 1
            max_grade = 2

            # MP3 to MP11: Horseshoe Bay
            2 miles 1 track
            # MP19 to MP20: Brunswick Siding
            siding warp=brunswick
            """
        )
        self.assertIn("# header stays with the paste", rendered)
        self.assertIn("# MP3 to MP11: Horseshoe Bay", rendered)
        self.assertIn("# MP19 to MP20: Brunswick Siding", rendered)
        namespace = _exec_block(rendered)
        mainline = namespace["Mainline"]
        literal = _mainline(rendered)
        self.assertEqual(literal, mainline)
        self.assertEqual(mainline[0][0], (0, 0))
        self.assertAlmostEqual(mainline[0][1], 2.4)
        self.assertEqual(
            mainline[0][2],
            {"min_radius": 2, "min_grade": 1, "max_grade": 2},
        )
        self.assertEqual(mainline[1][0], (0, 1))
        self.assertAlmostEqual(mainline[1][1], 0.6)
        self.assertEqual(namespace["Warps"][0]["name"], "brunswick")
        for run in mainline:
            self.assertIsInstance(run, list)
            self.assertIsInstance(run[0], tuple)
            self.assertEqual(len(run[0]), 2)
            self.assertIsInstance(run[1], (int, float))
            self.assertIsInstance(run[2], dict)
        cumulative = aggregate_track_profile(mainline)
        self.assertAlmostEqual(cumulative[-1][1], tools.inches(3.0))
        self.assertEqual(cumulative[0][0], (0, 0))
        self.assertEqual(cumulative[1][2]["min_radius"], 2)

    def test_cli_writes_the_same_text(self):
        body = "target_miles = 1\nladder_allowance = 0\n1 miles 1 track\n"
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "route.txt")
            output = os.path.join(folder, "out.txt")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(body)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main([source, "--out", output])
            self.assertEqual(code, 0)
            with open(output, "r", encoding="utf-8") as handle:
                written = handle.read()
            self.assertEqual(written, stdout.getvalue())
            self.assertIn("Mainline = [", written)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main([os.path.join(folder, "missing.txt")])
            self.assertEqual(code, 1)
            self.assertIn("route builder:", stderr.getvalue())


class ExampleTests(unittest.TestCase):
    def test_vancouver_squamish_example(self):
        path = os.path.join(ROOT, "routes", "example_vancouver_squamish.txt")
        with open(path, "r", encoding="utf-8") as handle:
            route, rendered = build(handle.read())

        self.assertAlmostEqual(
            route.fixed_total + route.flex_total + route.ladder_total,
            6.0,
        )
        self.assertAlmostEqual(route.fixed_total, 0.75)
        self.assertAlmostEqual(route.ladder_total, 4 * tools.miles(1536))
        self.assertEqual(route.ladder_step_units, 1536)

        by_name = {" / ".join(seg.comments): seg for seg in route.segments}
        bridge = by_name["MP11: Horseshoe Bay bridge"]
        tunnel = by_name["MP20 to MP27: tunnel"]
        station = by_name["MP27 to MP28: Porteau station"]
        siding = by_name["MP19 to MP20: Brunswick Siding"]
        shop = by_name["MP38 to MP39: Squamish shop"]
        yard = route.segments[-1]

        self.assertEqual(bridge.mode, "clamped min")
        self.assertAlmostEqual(bridge.miles, 0.2)
        self.assertEqual(bridge.params["straight_only"], True)
        self.assertEqual(bridge.params["min_grade"], 1)
        self.assertEqual(tunnel.params["straight_only"], True)
        self.assertGreater(tunnel.miles, 0.2)
        self.assertEqual(station.params["flat"], True)
        self.assertNotIn("min_grade", station.params)
        self.assertNotIn("max_grade", station.params)
        self.assertEqual(siding.tracks, (0, 1))
        self.assertAlmostEqual(siding.miles, 0.6)
        self.assertEqual(shop.tracks, (0, 2))
        self.assertAlmostEqual(shop.miles, 0.15)
        self.assertEqual(yard.mode, "handbuilt")

        # Ambleside and Horseshoe Bay are the same run, so their comments join.
        self.assertIn(
            "MP3 to MP8: Ambleside + MP8 to MP11: Horseshoe Bay",
            rendered,
        )
        self.assertNotIn("handbuilt", rendered.split("Mainline = ", 1)[1])

        namespace = _exec_block(rendered)
        mainline = namespace["Mainline"]
        self.assertEqual(_mainline(rendered), mainline)
        names = [warp["name"] for warp in namespace["Warps"]]
        self.assertEqual(names, ["brunswick", "squamish"])
        self.assertAlmostEqual(namespace["Warps"][0]["mile"], siding.milepost_start, places=5)
        self.assertAlmostEqual(namespace["Warps"][1]["mile"], shop.milepost_start, places=5)
        plain = sum(run[1] for run in mainline)
        # Printed miles are 6 decimal places. The leftover is a fraction of an inch.
        self.assertAlmostEqual(plain + route.ladder_total, 6.0, places=5)
        cumulative = aggregate_track_profile([run[:] for run in mainline])
        self.assertAlmostEqual(tools.miles(cumulative[-1][1]), plain)
        for run in mainline:
            self.assertEqual(len(run), 3)
            self.assertEqual(len(run[0]), 2)


if __name__ == "__main__":
    unittest.main()
