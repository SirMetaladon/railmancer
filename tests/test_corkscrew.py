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

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, lines, sectors

# Captured at import. test_cascadia_sidings replaces write_bezier_points
# and does not put it back.
_WRITE_BEZIER = lines.write_bezier_points

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
        if cfg.get("sector_corkscrew_prefer_height") != 1:
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
        # The fixture's floor step is 3200, past the shipped cliff of 1000.
        # This test is about which corkscrew link breaks, so the cliff stays open.
        cfg.CFG["sector_connection_maximum_cliff"] = 100000

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


class SectorLinkTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        cfg.CFG["sector_real_size"] = SIZE
        cfg.CFG["sector_minimum_height"] = 16
        cfg.CFG["sector_connection_maximum_cliff"] = 1000

    def tearDown(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()

    def test_floor_cliff_cuts_the_link_and_a_ceiling_gap_does_not(self):

        # 0..4000 next to 3000..6000 still overlaps, but the floors are
        # 2992 apart, past the 1000 cliff. A short ceiling on the same floor
        # stays linked.
        sectors.new_sector(0, 0, 0, 4000)
        sectors.new_sector(1, 0, 3000, 6000)
        self.assertFalse(
            sectors.sectors_are_connected(
                sectors.Sectors["0x0x0"], sectors.Sectors["1x0x187"]
            )
        )
        self.assertIs(
            sectors.get_sector_relative_to_this_sector(sectors.Sectors["0x0x0"], [1, 0]),
            False,
        )

        sectors.new_sector(0, 1, 0, 2000)
        sectors.new_sector(1, 1, 0, 8000)
        low = sectors.Sectors["0x1x0"]
        high = sectors.Sectors["1x1x0"]
        self.assertTrue(sectors.sectors_are_connected(low, high))
        self.assertEqual(
            sectors.get_sector_relative_to_this_sector(low, [1, 0]), high["id"]
        )

    def test_neighbor_is_the_sector_with_the_closest_floor(self):

        # The upper sector overlaps more (400 vs 200 in stored units). The
        # old largest-overlap walk linked that one. The short sector shares
        # this floor, and that is the wall.
        cfg.CFG["sector_connection_maximum_cliff"] = 5000
        sectors.new_sector(0, 0, 0, 8000)
        sectors.new_sector(1, 0, 0, 3200)
        sectors.new_sector(1, 0, 1600, 8000)
        chosen = sectors.get_sector_relative_to_this_sector(
            sectors.Sectors["0x0x0"], [1, 0]
        )
        self.assertEqual(chosen, "1x0x0")

    def test_equal_floor_gap_prefers_overlap_then_the_earlier_sector(self):

        # Both neighbors are 1600 off this floor. The higher one overlaps
        # more, so it wins even though the lower one was created first.
        cfg.CFG["sector_connection_maximum_cliff"] = 5000
        sectors.new_sector(0, 0, 1600, 8000)
        sectors.new_sector(1, 0, 0, 4000)
        sectors.new_sector(1, 0, 3200, 9600)
        chosen = sectors.get_sector_relative_to_this_sector(
            sectors.Sectors["0x0x100"], [1, 0]
        )
        self.assertEqual(chosen, "1x0x200")

        # Same floor gap and the same overlap. The earlier sector keeps it.
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        sectors.new_sector(0, 0, 1600, 6400)
        sectors.new_sector(1, 0, 0, 4800)
        sectors.new_sector(1, 0, 3200, 8000)
        chosen = sectors.get_sector_relative_to_this_sector(
            sectors.Sectors["0x0x100"], [1, 0]
        )
        self.assertEqual(chosen, "1x0x0")


class TrackBoundaryTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def tearDown(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        lines.Beziers.clear()
        lines.sampled_points = []

    def test_no_sampled_track_crosses_an_unlinked_cardinal_boundary(self):

        # Heights build_fit gives a rail at z=0 beside a rail at z=1800.
        # The tall sector is 5200 tall (minimum height + maximum height).
        # It overlaps the upper stack by 3408 and the lower sector, which
        # shares its floor, by 1760. The upper floor is 1792 higher, inside
        # the shipped cliff of 2000. Largest-overlap links the upper sector;
        # link() then drops the lower sector's link, and this rail hits a wall.
        saved = {
            key: cfg.CFG[key]
            for key in (
                "sector_real_size",
                "sector_minimum_height",
                "sector_connection_maximum_cliff",
                "line_maximum_poll_point_distance",
            )
        }
        cfg.CFG["sector_real_size"] = SIZE
        cfg.CFG["sector_minimum_height"] = 1200
        cfg.CFG["sector_connection_maximum_cliff"] = 2000
        cfg.CFG["line_maximum_poll_point_distance"] = 80
        try:
            sectors.new_sector(0, 0, -304, 4896)
            sectors.new_sector(1, 0, -304, 1456)
            sectors.new_sector(1, 0, 1488, 6688)
            tall = sectors.Sectors["0x0x-19"]
            lower = sectors.Sectors["1x0x-19"]
            upper = sectors.Sectors["1x0x93"]
            self.assertEqual(
                sectors.get_sector_relative_to_this_sector(tall, [1, 0]),
                lower["id"],
            )

            start = np.array([200.0, 512.0, 0.0])
            end = np.array([200.0 + SIZE, 512.0, 0.0])
            # Straight cubic, same handles convert_nodes_to_bezier would use.
            # Appended directly: other tests replace lines.write_bezier_points
            # and leave that replacement in place.
            lines.Beziers.clear()
            lines.Beziers.append(
                (
                    start,
                    start * (2.0 / 3.0) + end * (1.0 / 3.0),
                    start * (1.0 / 3.0) + end * (2.0 / 3.0),
                    end,
                )
            )
            output = io.StringIO()
            with redirect_stdout(output):
                lines.encode_lines()
                sectors.link()

            step = cfg.get("line_maximum_poll_point_distance")
            saw_boundary = False
            for bezier in lines.Beziers:
                previous = None
                for point in lines.convert_bezier_to_points(bezier, step):
                    sector_id = sectors.get_sector_id_at_position(point)
                    self.assertTrue(
                        sector_id, f"track point {point} is outside every sector"
                    )
                    if previous and previous != sector_id:
                        first = sectors.Sectors[previous]
                        second = sectors.Sectors[sector_id]
                        self.assertEqual(
                            abs(first["x"] - second["x"]) + abs(first["y"] - second["y"]),
                            1,
                            f"track step {previous} -> {sector_id} is not cardinal",
                        )
                        saw_boundary = True
                        self.assertTrue(
                            sectors.sectors_share_a_wall(first, second),
                            f"track crosses an unlinked boundary {previous} -> {sector_id} at {point}",
                        )
                    previous = sector_id

            self.assertTrue(saw_boundary)
            self.assertEqual(tall["neighbors"][1], lower["id"])
            self.assertEqual(lower["neighbors"][3], tall["id"])
            self.assertIs(upper["neighbors"][3], False)
            self.assertNotIn("CORKSCREW ERROR", output.getvalue())
        finally:
            cfg.CFG.update(saved)


class WallClearanceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        self._size = cfg.CFG["sector_real_size"]
        cfg.CFG["sector_real_size"] = SIZE

    def tearDown(self):

        cfg.CFG["sector_real_size"] = self._size
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()

    def _open(self, x, y):

        sectors.new_sector(x, y, 0, 1600)
        sector = sectors.Sectors[f"{x}x{y}x0"]
        sector["neighbors"] = [False, False, False, False]
        return sector

    def test_distance_uses_unlinked_sides_and_the_fixed_buckets(self):

        sector = self._open(0, 0)
        close = sectors.measure_wall_clearance([[(32.0, 512.0, 800.0)]])
        self.assertEqual(close["count"], 1)
        self.assertAlmostEqual(close["min"], 32.0)
        self.assertEqual(close["under"], 1)
        self.assertEqual(close["histogram"][0], ("0-64", 1))

        # 64 is the collision line and the bucket edge. It is not a hit,
        # and it belongs to the next bucket.
        on_line = sectors.measure_wall_clearance([[(64.0, 512.0, 800.0)]])
        self.assertEqual(on_line["under"], 0)
        self.assertEqual(on_line["histogram"][1], ("64-256", 1))

        # The shared side is linked, so a point 16 from it is still half a
        # sector from the north and south walls.
        east = self._open(1, 0)
        sector["neighbors"][1] = east["id"]
        east["neighbors"][3] = sector["id"]
        beside = sectors.measure_wall_clearance([[(SIZE - 16.0, 512.0, 800.0)]])
        self.assertAlmostEqual(beside["min"], 512.0)
        self.assertEqual(beside["under"], 0)
        self.assertEqual(beside["crossings"], 0)

    def test_distance_caps_at_sector_size_inside_a_linked_block(self):

        offsets = ((0, 1), (1, 0), (0, -1), (-1, 0))
        for x in range(3):
            for y in range(3):
                self._open(x, y)
        for x in range(3):
            for y in range(3):
                sector = sectors.Sectors[f"{x}x{y}x0"]
                neighbors = []
                for dx, dy in offsets:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < 3 and 0 <= ny < 3:
                        neighbors.append(f"{nx}x{ny}x0")
                    else:
                        neighbors.append(False)
                sector["neighbors"] = neighbors

        stats = sectors.measure_wall_clearance([[(SIZE + 512.0, SIZE + 512.0, 800.0)]])
        # The outer walls sit 1536 away. The cap keeps the sample at one sector.
        self.assertAlmostEqual(stats["min"], float(SIZE))
        self.assertEqual(stats["max"], float(SIZE))
        self.assertEqual(stats["histogram"][-1][0], "1632+")

    def test_unlinked_cardinal_step_is_a_crossing_and_a_link_is_not(self):

        left = self._open(0, 0)
        right = self._open(1, 0)
        curve = [[(512.0, 512.0, 800.0), (SIZE + 512.0, 512.0, 800.0)]]
        open_stats = sectors.measure_wall_clearance(curve)
        self.assertEqual(open_stats["crossings"], 1)
        self.assertEqual(open_stats["pairs"], 1)
        self.assertEqual(open_stats["worst"][0]["sector"], left["id"])

        left["neighbors"][1] = right["id"]
        right["neighbors"][3] = left["id"]
        linked = sectors.measure_wall_clearance(curve)
        self.assertEqual(linked["crossings"], 0)
        self.assertEqual(linked["pairs"], 0)

    def test_handmade_map_edge_is_excluded_and_the_rest_is_kept(self):

        # Sector -5 is the west edge: sectors_per_map is 10, so column -6
        # is outside the grid. SIZE is the sector width in this test.
        edge_x = -5 * SIZE
        handmade = [lines.SOURCE_HANDMADE]
        generated = [lines.SOURCE_TRACKHAMMER]
        edge_point = [(edge_x + 32.0, 512.0, 800.0)]

        self._open(-5, 0)
        dropped = sectors.measure_wall_clearance([edge_point], handmade)
        self.assertEqual(dropped["count"], 0)
        self.assertEqual(dropped["excluded"], 1)
        self.assertEqual(dropped["under"], 0)
        self.assertEqual(dropped["worst"], [])
        self.assertEqual(dropped["missed"], [])

        kept = sectors.measure_wall_clearance([edge_point], generated)
        self.assertEqual(kept["count"], 1)
        self.assertEqual(kept["excluded"], 0)
        self.assertAlmostEqual(kept["min"], 32.0)
        self.assertEqual(kept["worst"][0]["source"], lines.SOURCE_TRACKHAMMER)
        self.assertEqual(kept["worst"][0]["wall"], "map-edge")
        self.assertEqual(kept["worst"][0]["wall_side"], "W")

        # An empty column inside the grid is not the map edge.
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        self._open(0, 0)
        interior_open = sectors.measure_wall_clearance(
            [[(32.0, 512.0, 800.0)]], handmade
        )
        self.assertEqual(interior_open["excluded"], 0)
        self.assertAlmostEqual(interior_open["min"], 32.0)
        self.assertEqual(interior_open["worst"][0]["wall"], "open")
        self.assertEqual(interior_open["worst"][0]["source"], lines.SOURCE_HANDMADE)

        # A sector exists past this side, so the wall is internal even
        # though the two are not linked.
        self._open(1, 0)
        squeezed = sectors.measure_wall_clearance(
            [[(SIZE - 40.0, 512.0, 800.0)]], handmade
        )
        self.assertEqual(squeezed["excluded"], 0)
        self.assertAlmostEqual(squeezed["min"], 40.0)
        self.assertEqual(squeezed["under"], 1)
        self.assertEqual(squeezed["worst"][0]["wall"], "internal")
        self.assertEqual(squeezed["worst"][0]["wall_side"], "E")

        # Same edge sector, but the internal wall is the closer one.
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        self._open(-5, 0)
        self._open(-4, 0)
        inner = (-4 * SIZE - 40.0, 512.0, 800.0)
        beside_break = sectors.measure_wall_clearance([[inner]], handmade)
        self.assertEqual(beside_break["excluded"], 0)
        self.assertAlmostEqual(beside_break["min"], 40.0)
        self.assertEqual(beside_break["worst"][0]["wall"], "internal")

        # Past the grid. Column -6 is not a sector, and it is not a
        # clearance of 0.
        outside = sectors.measure_wall_clearance(
            [[(edge_x - 80.0, 512.0, 800.0)]], handmade
        )
        self.assertEqual(outside["count"], 0)
        self.assertEqual(outside["excluded"], 0)
        self.assertEqual(len(outside["missed"]), 1)
        self.assertIsNone(outside["min"])

    def test_bezier_source_marks_handmade_and_trackhammer(self):

        saved = list(lines.Beziers)
        lines.Beziers.clear()
        try:
            _WRITE_BEZIER((0, 0, 0), (128, 0, 0), (1, 0, 0), (1, 0, 0))
            self.assertEqual(lines.Beziers[-1].source, lines.SOURCE_HANDMADE)
            _WRITE_BEZIER(
                (0, 0, 0),
                (128, 0, 0),
                (1, 0, 0),
                (1, 0, 0),
                source=lines.SOURCE_TRACKHAMMER,
            )
            self.assertEqual(lines.Beziers[-1].source, lines.SOURCE_TRACKHAMMER)
            self.assertEqual(len(lines.Beziers[-1]), 4)
        finally:
            lines.Beziers[:] = saved


if __name__ == "__main__":
    unittest.main()
