"""Switch stands measure track, and hammer switches get a stand.

Collapse keeps the option farther from the rails. The tree is the track
samples only, in 3D, so a staged ground hint cannot shove the stand, and a
track high above does not count as a neighbor. A hammer siding uses the
same two-option stand and gravel as an imported switch, on one lever id.
"""

import io
import os
import sys
import types
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

import numpy as np

from railmancer import lines, parser, sectors, tools, track, vmfpy
from railmancer.switches import place_transition

# Other suites replace vmfpy.add_entity and do not put it back.
_ADD_ENTITY = vmfpy.add_entity


class SwitchStandTests(unittest.TestCase):

    def setUp(self):

        self._entities = vmfpy.Entities
        self._add_entity = vmfpy.add_entity
        vmfpy.add_entity = _ADD_ENTITY
        self._sampled = lines.sampled_points
        self._staged = list(lines.staged_points)
        self._beziers = lines.Beziers
        self._library = track.track_model_library
        self._cache = track.valid_tracks_cache
        self._write_bezier = lines.write_bezier_points
        self._create_straight = track.create_straight
        vmfpy.Entities = []
        lines.sampled_points = []
        lines.staged_points = []
        lines.Beziers = []
        lines.write_bezier_points = lambda *_args, **_kwargs: None
        track.track_model_library = {}
        track.valid_tracks_cache = {}

    def tearDown(self):

        vmfpy.Entities = self._entities
        vmfpy.add_entity = self._add_entity
        lines.sampled_points = self._sampled
        lines.staged_points = self._staged
        lines.Beziers = self._beziers
        lines.write_bezier_points = self._write_bezier
        track.track_model_library = self._library
        track.valid_tracks_cache = self._cache
        track.create_straight = self._create_straight

    def test_collapse_picks_the_side_away_from_track_and_ignores_hints(self):

        near = (0.0, 100.0, 0.0)
        far = (0.0, -100.0, 0.0)
        # Track sits next to the first option. A hint sits on the second.
        # Counting the hint would make the first option the farther one.
        lines.sampled_points = [(0.0, 90.0, 0.0)]
        lines.staged_points = [far]
        vmfpy.add_entity(
            [
                ["collapse", near, far],
                {"name": "near"},
                {"name": "far"},
            ]
        )
        sectors.collapse_quantum_switchstands()
        self.assertEqual(vmfpy.get_entities()[0]["name"], "far")

    def test_collapse_uses_3d_distance_so_a_high_track_does_not_decide(self):

        # First option is the nearer neighbor in XY of a track far overhead.
        # Second option is the nearer neighbor in 3D of a track at stand height.
        # A flat distance would keep the second option.
        first = (0.0, 50.0, 0.0)
        second = (0.0, -50.0, 0.0)
        lines.sampled_points = [(0.0, 40.0, 1000.0), (0.0, -80.0, 0.0)]
        vmfpy.add_entity(
            [
                ["collapse", first, second],
                {"name": "first"},
                {"name": "second"},
            ]
        )
        sectors.collapse_quantum_switchstands()
        self.assertEqual(vmfpy.get_entities()[0]["name"], "first")

    def test_no_track_placeholder_ties_and_keeps_the_second_option(self):

        # Farther from the sentinel than the second option. Querying that
        # placeholder as if it were rail would keep this one.
        first = (-100000.0, -100000.0, 0.0)
        second = (100000.0, 100000.0, 0.0)
        lines.sampled_points = [[100000, 100000, 100000]]
        vmfpy.add_entity(
            [
                ["collapse", first, second],
                {"name": "first"},
                {"name": "second"},
            ]
        )
        sectors.collapse_quantum_switchstands()
        self.assertEqual(vmfpy.get_entities()[0]["name"], "second")

        vmfpy.Entities = []
        lines.sampled_points = []
        vmfpy.add_entity(
            [
                ["collapse", first, second],
                {"name": "first"},
                {"name": "second"},
            ]
        )
        sectors.collapse_quantum_switchstands()
        self.assertEqual(vmfpy.get_entities()[0]["name"], "second")

    def test_imported_switch_uses_the_shared_stand(self):

        entity = {
            "pos": (16.0, 32.0, 48.0),
            "mdl": "models/trakpak3_rsg/switches/sidings/example_mn.mdl",
            "skin": "0",
            "ang": (0.0, 90.0, 0.0),
            "visgroup": "25",
        }
        data = [
            {
                "StartDirection": "0fw",
                "EndDirection": "0fw",
                "Move": [-128, 0, 0],
            }
        ]
        parser.add_entity_to_new_map(entity, data)
        switch, stand, gravel = vmfpy.get_entities()
        self.assertEqual(switch["classname"], "tp3_switch")
        self.assertEqual(switch["lever"], stand[1]["lever"])
        self.assertEqual(switch["lever"], stand[2]["lever"])
        self.assertEqual(stand[1]["classname"], "tp3_switch_lever_anim")
        self.assertEqual(stand[1]["visgroup"], "23")
        self.assertEqual(stand[1]["ang"], (0, 90.0, 0))
        self.assertEqual(stand[2]["ang"], (0, 270.0, 0))
        self.assertEqual(gravel[1]["classname"], "prop_static")
        self.assertIn("ballast_pile_switch", gravel[1]["mdl"])
        self.assertEqual(gravel[1]["visgroup"], "23")
        # 110 back and 100 to the side, yaw 90, then down 17.5.
        self.assertTrue(np.allclose(stand[0][1], (116.0, -78.0, 30.5)))
        self.assertTrue(np.allclose(stand[0][1], stand[1]["pos"]))
        self.assertTrue(np.allclose(stand[0][2], stand[2]["pos"]))
        self.assertTrue(np.allclose(gravel[0][1], stand[0][1]))

    def test_hammer_siding_gets_a_lever_stand_and_gravel(self):

        track.create_straight = lambda *_args, **_kwargs: None
        # 4lt right is a gm_cascadia siding under switches/sidings/.
        place_transition((0.0, 0.0, 0.0), "4lt", 0, (0, 0), (0, 1))
        ents = vmfpy.get_entities()
        switches = [
            ent
            for ent in ents
            if isinstance(ent, dict) and ent.get("classname") == "tp3_switch"
        ]
        self.assertEqual(len(switches), 1)
        switch = switches[0]
        self.assertIn("/switches/sidings/", switch["mdl"].replace("\\", "/"))
        self.assertIn("p4lt_right_minr2048", switch["mdl"])
        lever = switch["lever"]
        self.assertTrue(lever.startswith("switch_"))

        collapses = [ent for ent in ents if isinstance(ent, list)]
        self.assertEqual(len(collapses), 2)
        stand = next(ent for ent in collapses if ent[1]["classname"] == "tp3_switch_lever_anim")
        gravel = next(ent for ent in collapses if ent[1]["classname"] == "prop_static")
        self.assertEqual(stand[1]["lever"], lever)
        self.assertEqual(stand[2]["lever"], lever)
        self.assertEqual(stand[1]["visgroup"], "23")
        self.assertEqual(gravel[1]["visgroup"], "23")
        self.assertIn("bethlehem_51a_right", stand[1]["mdl"])
        self.assertIn("ballast_pile_switch", gravel[1]["mdl"])

        start = track.track_model_library[switch["mdl"]]["StartDirection"]
        self.assertEqual(start, "4lt")
        stand_angle = float(switch["ang"][1]) + track.direction_to_angle(start)
        expected = np.add(
            switch["pos"], tools.rot3(np.array([-110.0, -100.0, -17.5]), stand_angle)
        )
        self.assertTrue(np.allclose(stand[0][1], expected))

        # Track on the first stand, hint on the second. Collapse keeps the second.
        lines.sampled_points = [tuple(float(value) for value in stand[0][1])]
        lines.staged_points = [tuple(float(value) for value in stand[0][2])]
        sectors.collapse_quantum_switchstands()
        collapsed = vmfpy.get_entities()
        self.assertTrue(all(isinstance(ent, dict) for ent in collapsed))
        chosen_stand = next(
            ent for ent in collapsed if ent.get("classname") == "tp3_switch_lever_anim"
        )
        chosen_gravel = next(
            ent for ent in collapsed if "ballast_pile_switch" in ent.get("mdl", "")
        )
        self.assertEqual(chosen_stand["lever"], lever)
        self.assertEqual(chosen_stand["ang"], stand[2]["ang"])
        self.assertEqual(chosen_gravel["ang"], gravel[2]["ang"])
        kept = next(ent for ent in collapsed if ent.get("classname") == "tp3_switch")
        self.assertEqual(kept["lever"], lever)

        vmfpy.ID = 1000
        leftover = [
            ["collapse", (0, 0, 0), (1, 0, 0)],
            {"mdl": "SHOULD_NOT_APPEAR"},
            {"mdl": "ALSO_NO"},
        ]
        with redirect_stdout(io.StringIO()):
            text = vmfpy.synthesize_entities(collapsed + [leftover])
        self.assertIn(lever, text)
        self.assertIn("tp3_switch_lever_anim", text)
        self.assertIn("ballast_pile_switch", text)
        self.assertNotIn("SHOULD_NOT_APPEAR", text)
