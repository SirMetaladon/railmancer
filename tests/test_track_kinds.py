"""Track ends, bumpers, bends, M turnouts, and hammer-switch points.

Parsed switches already put both legs on the point list. A switch the
track hammer creates has to do the same, from the same model.
"""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import numpy as np

from railmancer import cfg, lines, track, tools, vmfpy
from railmancer.switches import place_transition, register_switch_library, select_switch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Other suites replace this with a no-op and do not put it back.
_WRITE_BEZIER = lines.write_bezier_points

END_0FW = "models/trakpak3_rsg/spl/trackends/end_ang0fw.mdl"
END_1LT = "models/trakpak3_rsg/spl/trackends/end_ang1lt.mdl"
END_1RT = "models/trakpak3_rsg/spl/trackends/end_ang1rt.mdl"
END_4LT = "models/trakpak3_rsg/spl/trackends/end_ang4lt.mdl"
CARSTOP = "models/trakpak3_rsg/spl/bumpers/carstop_ang0fw.mdl"
KNUCKLE = "models/trakpak3_rsg/spl/bumpers/bumper_knuckle_ang2rt.mdl"
BEND = "models/trakpak3_rsg/bends/b0fw_right_minr2048_0pg_+0640x+0032x0000.mdl"
BEND_GRADED = "models/trakpak3_rsg/bends/b4lt_right_minr8192_22pg_+2176x-1920x+064up.mdl"
M_DV = "models/trakpak3_rsg/switches/str_bez/m2rt_4rt_right_minr2048_+0832x+0416_+0736x+0512_dv.mdl"
M_MN = "models/trakpak3_rsg/switches/str_bez/m2rt_4rt_right_minr2048_+0832x+0416_+0736x+0512_mn.mdl"
M_OTHER = "models/trakpak3_rsg/switches/str_bez/m4rt_2rt_left_minr2048_+0512x+0512_+0672x+0480_mn.mdl"
STRAIGHT = "models/trakpak3_rsg/straights/s0128_0fw_0pg_+0128x00000x0000.mdl"


def _round_point(point):

    return tuple(round(float(component), 3) for component in point)


def _sample(routes, pos, yaw):

    lines.Beziers = []
    for route in routes:
        track.add_lines_from_track(pos, route, yaw)
    lines.encode_lines()
    return [_round_point(point) for point in lines.sampled_points]


class TrackKindTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):

        self._library = track.track_model_library
        self._cache = track.valid_tracks_cache
        self._straights = track.track_straight_cache
        self._beziers = lines.Beziers
        self._points = lines.sampled_points
        self._add_entity = vmfpy.add_entity
        self._create_straight = track.create_straight
        self._write_bezier = lines.write_bezier_points
        lines.write_bezier_points = _WRITE_BEZIER
        track.track_model_library = {}
        track.valid_tracks_cache = {}
        track.track_straight_cache = {}
        lines.Beziers = []
        lines.sampled_points = []

    def tearDown(self):

        track.track_model_library = self._library
        track.valid_tracks_cache = self._cache
        track.track_straight_cache = self._straights
        lines.Beziers = self._beziers
        lines.sampled_points = self._points
        vmfpy.add_entity = self._add_entity
        track.create_straight = self._create_straight
        lines.write_bezier_points = self._write_bezier

    def test_track_end_is_128_along_its_rotated_direction(self):

        for model, direction in (
            (END_0FW, "0fw"),
            (END_1LT, "1lt"),
            (END_1RT, "1rt"),
            (END_4LT, "4lt"),
        ):
            routes = track.process_file(model)
            self.assertEqual(len(routes), 1)
            self.assertEqual(routes[0]["StartDirection"], direction)
            self.assertEqual(routes[0]["EndDirection"], direction)
            self.assertNotIn(model, track.track_straight_cache)
            move = np.array(routes[0]["Move"][:2], dtype=float)
            self.assertAlmostEqual(float(np.linalg.norm(move)), 128.0, places=5)
            for yaw in (0, 90, -90):
                points = _sample(routes, (0.0, 0.0, 0.0), yaw)
                self.assertEqual(points[0], (0.0, 0.0, 0.0))
                end = np.array(points[-1][:2], dtype=float)
                heading = np.array(
                    tools.rot_orth(track.get_heading(direction), yaw)[:2], dtype=float
                )
                heading = heading / np.linalg.norm(heading)
                # Bezier sampling lands on the endpoint within a fraction of a unit.
                self.assertAlmostEqual(float(np.dot(end, heading)), 128.0, delta=0.05)
                self.assertLess(float(np.linalg.norm(end - 128.0 * heading)), 0.05)

    def test_bumpers_print_nothing_and_add_no_points(self):

        for model in (CARSTOP, KNUCKLE):
            sink = io.StringIO()
            with redirect_stdout(sink):
                routes = track.process_file(model)
            self.assertEqual(routes, [])
            self.assertEqual(sink.getvalue(), "")
            lines.Beziers = []
            for route in routes:
                track.add_lines_from_track((0.0, 0.0, 0.0), route, 0)
            self.assertEqual(lines.Beziers, [])

    def test_bend_endpoints_follow_the_name(self):

        routes = track.process_file(BEND)
        self.assertEqual(routes[0]["StartDirection"], "0fw")
        self.assertEqual(routes[0]["EndDirection"], "0fw")
        self.assertEqual(routes[0]["Move"], [-640, 32, 0])
        self.assertEqual(routes[0]["RealGrade"], 0)
        points = _sample(routes, (0.0, 0.0, 0.0), 0)
        self.assertEqual(points[0], (0.0, 0.0, 0.0))
        self.assertEqual(points[-1], (-640.0, 32.0, 0.0))
        turned = _sample(routes, (0.0, 0.0, 0.0), 90)
        self.assertEqual(turned[-1], (-32.0, -640.0, 0.0))

        graded = track.process_file(BEND_GRADED)
        self.assertEqual(graded[0]["StartDirection"], "4lt")
        self.assertEqual(graded[0]["EndDirection"], "4lt")
        self.assertEqual(graded[0]["Move"], [-2176, -1920, 64])
        graded_points = _sample(graded, (0.0, 0.0, 0.0), 0)
        self.assertEqual(graded_points[-1], (-2176.0, -1920.0, 64.0))

    def test_m_turnout_legs_match_and_dv_equals_mn(self):

        diverging = track.process_file(M_DV)
        main = track.process_file(M_MN)
        self.assertEqual(diverging, main)
        self.assertEqual(diverging[0]["StartDirection"], "2rt")
        self.assertEqual(diverging[0]["EndDirection"], "2rt")
        self.assertEqual(diverging[0]["Move"], [-832, 416, 0])
        self.assertEqual(diverging[1]["StartDirection"], "2rt")
        self.assertEqual(diverging[1]["EndDirection"], "4rt")
        self.assertEqual(diverging[1]["Move"], [-736, 512, 0])
        points = _sample(diverging, (0.0, 0.0, 0.0), 0)
        self.assertIn((-832.0, 416.0, 0.0), points)
        self.assertIn((-736.0, 512.0, 0.0), points)

        other_mn = track.process_file(M_OTHER)
        other_dv = track.process_file(M_OTHER.replace("_mn.mdl", "_dv.mdl"))
        self.assertEqual(other_mn, other_dv)
        self.assertEqual(other_mn[0]["EndDirection"], "4rt")
        self.assertEqual(other_mn[0]["Move"], [-512, 512, 0])
        self.assertEqual(other_mn[1]["EndDirection"], "2rt")
        self.assertEqual(other_mn[1]["Move"], [-672, 480, 0])

    def test_library_keeps_bends_and_switches_out_of_the_pathfinder(self):

        with tempfile.TemporaryDirectory() as base:
            root = os.path.join(base, "models", "trakpak3_rsg")

            def touch(relative):
                path = os.path.join(root, relative)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "w").close()

            touch("spl/trackends/end_ang0fw.mdl")
            touch("spl/bumpers/carstop_ang0fw.mdl")
            touch("bends/b0fw_right_minr2048_0pg_+0640x+0032x0000.mdl")
            touch("straights/s0128_0fw_0pg_+0128x00000x0000.mdl")
            touch(
                "switches/str_bez/m2rt_4rt_right_minr2048_+0832x+0416_+0736x+0512_dv.mdl"
            )
            sink = io.StringIO()
            with redirect_stdout(sink):
                track.build_track_library(base, ".mdl")

        self.assertNotIn(END_0FW, track.track_model_library)
        self.assertNotIn(CARSTOP, track.track_model_library)
        self.assertIn(BEND, track.track_model_library)
        self.assertEqual(len(track.track_model_library[BEND]), 1)
        self.assertEqual(len(track.track_model_library[M_DV]), 2)
        self.assertIn(STRAIGHT, track.track_model_library)
        self.assertNotIn("No track-processing support", sink.getvalue())

        offered = track.valid_next_tracks(
            "0fw", {"min_radius": 0, "min_grade": 0, "max_grade": 1}
        )
        self.assertIn(STRAIGHT, offered)
        self.assertNotIn(BEND, offered)
        self.assertNotIn(M_DV, offered)
        self.assertNotIn(END_0FW, offered)

    def test_list_of_one_route_still_places_a_straight(self):

        route = track.process_file(STRAIGHT)[0]
        track.track_model_library[STRAIGHT] = [route]
        self.assertEqual(track.get_length(STRAIGHT), route["Length"])
        node = track.get_new_node_from_node_and_model(
            STRAIGHT, ([0, 0, 0], "0fw", 0, False)
        )
        self.assertEqual(int(node[0][0]), -128)

    def test_hammer_switch_points_match_a_parsed_switch(self):

        spec = select_switch("0fw", "left")
        routes = track.process_file(spec["dv"])
        self.assertEqual(len(routes), 2)
        # The far end of the library stores this list. Registering the
        # hammer record used to replace it with one dict.
        track.track_model_library[spec["dv"]] = routes
        track.track_model_library[spec["mn"]] = list(routes)
        register_switch_library()
        stored = track.track_model_library[spec["mn"]]
        self.assertEqual(stored["kind"], "switch")
        self.assertEqual(stored["GradeLevel"], 0)
        self.assertIn("Radius", stored)
        self.assertEqual(stored["routes"], routes)

        self._assert_placed_switch_matches_parsed(90)

        track.track_model_library = {}
        track.valid_tracks_cache = {}
        register_switch_library()
        self.assertEqual(len(track.track_model_library[spec["mn"]]["routes"]), 2)
        track.valid_next_tracks(
            "0fw", {"min_radius": 0, "min_grade": 0, "max_grade": 1}
        )
        track.valid_tracks_cache = {}
        offered = track.valid_next_tracks(
            "0fw", {"min_radius": 0, "min_grade": 0, "max_grade": 1}
        )
        self.assertFalse(any("/switches/" in name for name in offered))
        self._assert_placed_switch_matches_parsed(0)

    def _assert_placed_switch_matches_parsed(self, heading):

        placed = []
        track.create_straight = lambda *args, **kwargs: None
        vmfpy.add_entity = placed.append
        lines.Beziers = []
        place_transition((0.0, 0.0, 0.0), "0fw", heading, (0, 0), (0, 1))
        lines.encode_lines()
        hammer = [_round_point(point) for point in lines.sampled_points]
        switches = [
            prop
            for prop in placed
            if isinstance(prop, dict) and prop.get("classname") == "tp3_switch"
        ]
        self.assertEqual(len(switches), 1)
        prop = switches[0]
        parsed = _sample(track.process_file(prop["mdl"]), prop["pos"], prop["ang"][1])
        self.assertEqual(hammer, parsed)
        self.assertGreater(len(parsed), 2)
