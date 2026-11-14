"""Synthetic corkscrews for sectors.link.

Four sectors around one corner, with a second sector stacked on the start,
make a clockwise walk of four links land on the upper sector. Wider loops
and a plain 2x2 are not corkscrews and must stay linked.

Track samples are stubbed through lines.sampled_points, which
get_all_track_points returns. Heights passed to new_sector are map units.
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

from railmancer import cfg, lines, sectors

SIZE = 1024
LIMIT = 250

# Stored floors are map units / 16. Low band 0..1600, high band 3200..4800.
LOW = "0x0x0"
HIGH = "0x0x200"
NORTH = "0x1x0"
EAST = "1x0x200"
FAR = "1x1x0"


class CorkscrewTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))
        if cfg.get("sector_corkscrew_track_clearance") != 250:
            raise AssertionError("sector_corkscrew_track_clearance default")
        if cfg.get("sector_corkscrew_prefer_height") != 0:
            raise AssertionError("sector_corkscrew_prefer_height default")

    def tearDown(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        lines.sampled_points = []

    def _link_corkscrew(self, points, prefer_height):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        lines.sampled_points = list(points)
        cfg.CFG["sector_real_size"] = SIZE
        cfg.CFG["sector_minimum_height"] = 16
        cfg.CFG["sector_corkscrew_track_clearance"] = LIMIT
        cfg.CFG["sector_corkscrew_prefer_height"] = prefer_height

        # D (north) only overlaps the low sector. B (east) only overlaps the
        # high one. C spans both, so the walk north-east-south-west changes floor.
        sectors.new_sector(0, 0, 0, 1600)
        sectors.new_sector(0, 0, 3200, 4800)
        sectors.new_sector(1, 0, 3200, 4800)
        sectors.new_sector(1, 1, 0, 4800)
        sectors.new_sector(0, 1, 0, 1600)
        for sector_id in (LOW, HIGH, NORTH, EAST, FAR):
            self.assertIn(sector_id, sectors.Sectors)

        return self._run_link()

    def _run_link(self):

        calls = {"n": 0}
        original = lines.get_all_track_points

        def wrapped():
            calls["n"] += 1
            return original()

        lines.get_all_track_points = wrapped
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                sectors.link()
        finally:
            lines.get_all_track_points = original
        return output.getvalue(), calls["n"]

    def test_breaks_the_link_farthest_from_track(self):

        # north wall of the low sector is 50 away, the two walls of C are 100
        # away, and the high sector's east wall is exactly the clearance (250).
        text, reads = self._link_corkscrew(
            (
                (100, 974, 800),
                (1124, 1124, 800),
                (774, 400, 4000),
            ),
            prefer_height=0,
        )

        self.assertIs(sectors.Sectors[EAST]["neighbors"][3], False)
        self.assertIs(sectors.Sectors[HIGH]["neighbors"][1], False)
        self.assertEqual(sectors.Sectors[LOW]["neighbors"][0], NORTH)
        self.assertEqual(sectors.Sectors[NORTH]["neighbors"][1], FAR)
        self.assertEqual(sectors.Sectors[FAR]["neighbors"][2], EAST)
        self.assertEqual(sectors.Sectors[NORTH]["neighbors"][2], LOW)
        self.assertEqual(sectors.Sectors[FAR]["neighbors"][3], NORTH)
        self.assertEqual(sectors.Sectors[EAST]["neighbors"][0], FAR)
        self.assertIn("Broke corkscrew " + EAST + " west to " + HIGH + ", clearance 250.", text)
        self.assertNotIn("CORKSCREW ERROR", text)
        self.assertEqual(reads, 1)

    def test_prefer_height_breaks_the_biggest_floor_step(self):

        # The east-west link onto HIGH is the farthest from track (924) but
        # both sectors are floor 200. C down to B is only 300 away and is the
        # only floor change (0 vs 200). The other two walls are inside 250.
        text, reads = self._link_corkscrew(
            (
                (100, 974, 800),
                (974, 1500, 800),
                (2000, 1324, 800),
                (100, 400, 4000),
            ),
            prefer_height=1,
        )

        self.assertIs(sectors.Sectors[FAR]["neighbors"][2], False)
        self.assertIs(sectors.Sectors[EAST]["neighbors"][0], False)
        self.assertEqual(sectors.Sectors[EAST]["neighbors"][3], HIGH)
        self.assertEqual(sectors.Sectors[HIGH]["neighbors"][1], EAST)
        self.assertEqual(sectors.Sectors[LOW]["neighbors"][0], NORTH)
        self.assertEqual(sectors.Sectors[NORTH]["neighbors"][1], FAR)
        self.assertIn("Broke corkscrew " + FAR + " south to " + EAST + ", clearance 300.", text)
        self.assertNotIn("CORKSCREW ERROR", text)
        self.assertEqual(reads, 1)

    def test_track_inside_clearance_on_every_link_is_left_alone(self):

        text, reads = self._link_corkscrew(
            (
                (100, 974, 800),
                (974, 1500, 800),
                (1124, 1124, 800),
                (974, 400, 4000),
            ),
            prefer_height=0,
        )

        self.assertEqual(sectors.Sectors[LOW]["neighbors"][0], NORTH)
        self.assertEqual(sectors.Sectors[NORTH]["neighbors"][2], LOW)
        self.assertEqual(sectors.Sectors[NORTH]["neighbors"][1], FAR)
        self.assertEqual(sectors.Sectors[FAR]["neighbors"][3], NORTH)
        self.assertEqual(sectors.Sectors[FAR]["neighbors"][2], EAST)
        self.assertEqual(sectors.Sectors[EAST]["neighbors"][0], FAR)
        self.assertEqual(sectors.Sectors[EAST]["neighbors"][3], HIGH)
        self.assertEqual(sectors.Sectors[HIGH]["neighbors"][1], EAST)
        self.assertNotIn("Broke corkscrew", text)
        self.assertIn("CORKSCREW ERROR", text)
        self.assertIn("x=" + str(SIZE), text)
        self.assertIn("y=" + str(SIZE), text)
        self.assertIn(LOW, text)
        self.assertIn(HIGH, text)
        self.assertIn("floor 0 ceiling 1600", text)
        self.assertIn("floor 3200 ceiling 4800", text)
        self.assertEqual(reads, 1)

    def test_plain_square_is_untouched(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        lines.sampled_points = [(100, 974, 800)]
        cfg.CFG["sector_real_size"] = SIZE
        cfg.CFG["sector_minimum_height"] = 16
        cfg.CFG["sector_corkscrew_track_clearance"] = LIMIT
        cfg.CFG["sector_corkscrew_prefer_height"] = 0

        for x, y in ((0, 0), (1, 0), (0, 1), (1, 1)):
            sectors.new_sector(x, y, 0, 1600)

        text, reads = self._run_link()

        self.assertEqual(sectors.Sectors["0x0x0"]["neighbors"], ["0x1x0", "1x0x0", False, False])
        self.assertEqual(sectors.Sectors["1x0x0"]["neighbors"], ["1x1x0", False, False, "0x0x0"])
        self.assertEqual(sectors.Sectors["1x1x0"]["neighbors"], [False, False, "1x0x0", "0x1x0"])
        self.assertEqual(sectors.Sectors["0x1x0"]["neighbors"], [False, "1x1x0", "0x0x0", False])
        self.assertNotIn("Broke corkscrew", text)
        self.assertNotIn("CORKSCREW", text)
        self.assertEqual(reads, 0)


if __name__ == "__main__":
    unittest.main()
