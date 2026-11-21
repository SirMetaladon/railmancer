"""Sector brush groups, and the two output-identical speedups.

The sort and the edit splice are compared to the old algorithms, including
on a synthetic VMF, so a difference shows up as a failed equality rather
than a changed map.
"""

import os
import random
import sys
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, lines, sectors, vmfpy


def _legacy_inserter(stack, to_add):

    heuristic = to_add[1]
    for index, (_, height) in enumerate(stack):
        if heuristic > height:
            stack.insert(index, to_add)
            return
    stack.append(to_add)


def _legacy_buckets(points, sectors_per_map):

    buckets = {}
    for point in points:
        sector_x, sector_y = sectors.convert_real_to_sector_xy(point)
        if abs(sector_x + 0.5) > (sectors_per_map / 2):
            continue
        if abs(sector_y + 0.5) > (sectors_per_map / 2):
            continue
        key = f"{sector_x}x{sector_y}"
        item = ((sector_x, sector_y), -point[2])
        if buckets.get(key, False):
            _legacy_inserter(buckets[key], item)
        else:
            buckets[key] = [item]
    return buckets


def _legacy_apply(text, deletions, insertions):

    insertions = [
        (pos, chunk)
        for pos, chunk in insertions
        if chunk and not any(start <= pos < end for start, end in deletions)
    ]
    operations = [("del", start, end, "") for start, end in deletions]
    operations.extend(("ins", pos, pos, chunk) for pos, chunk in insertions)
    operations.sort(key=lambda item: item[1], reverse=True)
    for kind, start, end, chunk in operations:
        if kind == "del":
            text = text[:start] + text[end:]
        else:
            text = text[:start] + chunk + text[start:]
    return text


class FitSortTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def test_bucket_order_matches_the_old_inserter_including_ties(self):

        cfg.CFG["sector_real_size"] = 1024
        cfg.CFG["sectors_per_map"] = 8
        points = []
        for index in range(400):
            # Repeated heights, and the same height arriving in a known order.
            z = float((index * 17) % 9) * 100
            points.append((100 + (index % 3) * 1024, 200 + (index % 5) * 1024, z))
        points.append((100, 200, 100))
        points.append((100, 200, 100))
        new = sectors.sort_points_to_sector_grid_buckets(points, 8)
        old = _legacy_buckets(points, 8)
        self.assertEqual(new, old)


class EditSpliceTests(unittest.TestCase):

    def test_joined_edits_match_the_old_splice_on_a_vmf(self):

        # A small world with repeated solids, the shape _apply_edits rewrites.
        solid = (
            '    solid\n    {\n        "id" "10"\n        editor\n        {\n'
            '            "color" "0 0 0"\n        }\n    }\n'
        )
        text = "world\n{\n" + solid * 40 + "}\nentity\n{\n}\n"
        deletions = [(20, 80), (200, 260), (500, 540)]
        insertions = [
            (80, '        "visgroupid" "29"\n'),
            (260, '        "visgroupid" "29"\n'),
            (12, "visgroups\n{\n}\n"),
            (len(text) - 10, "NEWBRUSH\n"),
            (80, "SECOND\n"),
        ]
        self.assertEqual(
            vmfpy._apply_edits(text, deletions, insertions),
            _legacy_apply(text, deletions, insertions),
        )

        rng = random.Random(1)
        blob = "abcdefghijklmnopqrstuvwxyz" * 80
        for _ in range(30):
            cuts = []
            cursor = 0
            while cursor < len(blob) - 5:
                cursor += rng.randint(3, 20)
                end = min(len(blob), cursor + rng.randint(1, 8))
                if cursor < len(blob):
                    cuts.append((cursor, end))
                cursor = end
            puts = []
            for pos in range(0, len(blob), rng.randint(5, 15)):
                puts.append((pos, rng.choice(["X", "YY\n", ""])))
            self.assertEqual(
                vmfpy._apply_edits(blob, cuts, puts),
                _legacy_apply(blob, cuts, puts),
            )


class SectorGroupTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Group_Keys.clear()
        vmfpy.Entities.clear()
        vmfpy.Brush_Entites.clear()
        vmfpy.Sector_Group_IDs.clear()
        cfg.CFG["sector_real_size"] = 1024
        cfg.CFG["prop_group_subdivisions"] = 4

    def tearDown(self):

        vmfpy.Brushes.clear()
        vmfpy.Brush_Group_Keys.clear()
        vmfpy.Entities.clear()
        vmfpy.Brush_Entites.clear()
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()

    def test_one_group_per_sector_after_the_scatter_groups(self):

        sectors.new_sector(0, 0, 0, 1600)
        sectors.new_sector(1, 0, 0, 1600)
        low = sectors.Sectors["0x0x0"]
        side = sectors.Sectors["1x0x0"]
        vmfpy.floor(0, 0, 0, 1024, low["id"])
        vmfpy.wall(0, 0, 0, 1600, 0, 1024, "ceiling", low["id"])
        vmfpy.ceiling(1024, 0, 1600, 1024, side["id"])
        vmfpy.add_brush(
            [0, 64, 0, 64, 16, 32, "displacement", "tex", "\nDISP"],
            low["id"],
        )
        vmfpy.add_brush([200, 264, 0, 64, 0, 16, "floor"])
        vmfpy.Entities.append(
            {
                "pos": (10, 10, 100),
                "mdl": "models/props_foliage/tree_pine_tall_01.mdl",
                "ang": (0, 0, 0),
                "grouping": "tree",
                "sector_id": low["id"],
            }
        )

        with redirect_stdout(StringIO()):
            text = vmfpy.assemble_vmf()

        scatter_id = str(vmfpy.GROUP_ID_BASE)
        low_id = str(vmfpy.GROUP_ID_BASE + 1)
        side_id = str(vmfpy.GROUP_ID_BASE + 2)
        self.assertEqual(vmfpy.Entities[0]["groupid"], scatter_id)
        self.assertEqual(vmfpy.Sector_Group_IDs[low["id"]], low_id)
        self.assertEqual(vmfpy.Sector_Group_IDs[side["id"]], side_id)

        # Floor, wall, and displacement share the low sector. The unkeyed
        # brush is not in a group. The side ceiling is the other group.
        self.assertEqual(text.count(f'"groupid" "{low_id}"'), 3)
        self.assertEqual(text.count(f'"groupid" "{side_id}"'), 1)
        self.assertEqual(text.count(f'"groupid" "{scatter_id}"'), 1)
        self.assertIn(f'\n    group\n    {{\n        "id" "{low_id}"', text)
        self.assertIn(f'\n    group\n    {{\n        "id" "{side_id}"', text)
        self.assertLess(
            text.index(f'"id" "{scatter_id}"'), text.index(f'"id" "{low_id}"')
        )


if __name__ == "__main__":
    unittest.main()
