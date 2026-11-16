"""Hammer groups for scattered props.

One group per (sector, N x N subsector, category) with two or more props.
A single prop, a model with no category, and a non-prop entity stay loose.
"""

import os
import re
import sys
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, sectors, vmfpy

TREE_A = "models/props_foliage/tree_pine_tall_01.mdl"
TREE_B = "models/props_foliage/tree_pine_huge_snow.mdl"
ROCK_A = "models/props_wasteland/rockcliff_cluster01b.mdl"
ROCK_B = "models/props_forest/rock004.mdl"
COW = "models/props_2fort/cow001_reference.mdl"


def _prop(pos, model, **extra):
    ent = {"pos": pos, "mdl": model, "ang": (0, 0, 0)}
    ent.update(extra)
    return ent


class PropGroupTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):
        self._size = cfg.CFG["sector_real_size"]
        self._subs = cfg.CFG["prop_group_subdivisions"]
        self._categories = cfg.CFG["prop_group_categories"]
        cfg.CFG["sector_real_size"] = 1024
        cfg.CFG["prop_group_subdivisions"] = 4
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        vmfpy.Entities.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Entites.clear()

    def tearDown(self):
        cfg.CFG["sector_real_size"] = self._size
        cfg.CFG["prop_group_subdivisions"] = self._subs
        cfg.CFG["prop_group_categories"] = self._categories
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        vmfpy.Entities.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Entites.clear()

    def test_groups_by_sector_subsector_and_category(self):
        self.assertEqual(self._subs, 4)
        categories = cfg.get("prop_group_categories")
        self.assertIn(TREE_A, categories["trees"])
        self.assertIn(ROCK_B, categories["rocks"])

        # 1024 / 4 = 256. Low floor is 0..1600, high floor is 3200..4800.
        sectors.new_sector(0, 0, 0, 1600)
        sectors.new_sector(1, 0, 0, 1600)
        sectors.new_sector(0, 0, 3200, 4800)
        self.assertIn("0x0x0", sectors.Sectors)
        self.assertIn("1x0x0", sectors.Sectors)
        self.assertIn("0x0x200", sectors.Sectors)

        low_a = _prop((10, 10, 100), TREE_A)
        low_b = _prop((20, 40, 100), TREE_B)
        cell_a = _prop((300, 10, 100), TREE_A)
        cell_b = _prop((400, 20, 100), TREE_B)
        rock_a = _prop((30, 30, 100), ROCK_A)
        rock_b = _prop((50, 60, 100), ROCK_B)
        side_a = _prop((1030, 10, 100), TREE_A)
        side_b = _prop((1100, 20, 100), TREE_B)
        high_a = _prop((10, 10, 4000), TREE_A)
        high_b = _prop((20, 40, 4000), TREE_B)
        lone = _prop((10, 300, 100), TREE_A)
        cow = _prop((15, 15, 100), COW)
        switch = _prop(
            (12, 12, 100),
            TREE_A,
            classname="tp3_switch",
        )
        outside = _prop((9000, 10, 100), TREE_A)
        props = [
            low_a, low_b, cell_a, cell_b, rock_a, rock_b,
            side_a, side_b, high_a, high_b, lone, cow, switch, outside,
        ]

        self.assertEqual(vmfpy.scatter_bucket(low_a), ("0x0x0", 0, 0, "trees"))
        self.assertEqual(vmfpy.scatter_bucket(low_b), ("0x0x0", 0, 0, "trees"))
        self.assertEqual(vmfpy.scatter_bucket(cell_a), ("0x0x0", 1, 0, "trees"))
        self.assertEqual(vmfpy.scatter_bucket(rock_a), ("0x0x0", 0, 0, "rocks"))
        self.assertEqual(vmfpy.scatter_bucket(rock_b), ("0x0x0", 0, 0, "rocks"))
        self.assertEqual(vmfpy.scatter_bucket(side_a), ("1x0x0", 0, 0, "trees"))
        self.assertEqual(vmfpy.scatter_bucket(high_a), ("0x0x200", 0, 0, "trees"))
        self.assertEqual(vmfpy.scatter_bucket(lone), ("0x0x0", 0, 1, "trees"))
        self.assertIsNone(vmfpy.scatter_bucket(cow))
        self.assertIsNone(vmfpy.scatter_bucket(switch))
        self.assertIsNone(vmfpy.scatter_bucket(outside))

        vmfpy.Entities.extend(props)
        vmfpy.add_brush([0, 128, 0, 128, 0, 16, "floor"])
        with redirect_stdout(StringIO()):
            text = vmfpy.assemble_vmf()

        self.assertEqual(low_a["groupid"], low_b["groupid"])
        self.assertEqual(cell_a["groupid"], cell_b["groupid"])
        self.assertEqual(rock_a["groupid"], rock_b["groupid"])
        self.assertEqual(side_a["groupid"], side_b["groupid"])
        self.assertEqual(high_a["groupid"], high_b["groupid"])
        self.assertNotEqual(low_a["groupid"], cell_a["groupid"])
        self.assertNotEqual(low_a["groupid"], rock_a["groupid"])
        self.assertNotEqual(low_a["groupid"], side_a["groupid"])
        self.assertNotEqual(low_a["groupid"], high_a["groupid"])
        for loose in (lone, cow, switch, outside):
            self.assertNotIn("groupid", loose)

        by_group = {}
        for prop in props:
            gid = prop.get("groupid")
            if gid:
                by_group.setdefault(gid, []).append(prop)
        self.assertEqual(len(by_group), 5)
        self.assertEqual(len(set(by_group)), 5)
        for members in by_group.values():
            self.assertGreaterEqual(len(members), 2)
            self.assertEqual(len({vmfpy.scatter_bucket(m) for m in members}), 1)

        block_ids = re.findall(r'\n    group\n    \{\n        "id" "(\d+)"', text)
        ref_ids = re.findall(r'"groupid" "(\d+)"', text)
        self.assertEqual(sorted(block_ids), sorted(set(ref_ids)))
        self.assertEqual(len(block_ids), 5)
        self.assertEqual(len(ref_ids), 10)
        self.assertTrue(all(ref_ids.count(gid) >= 2 for gid in block_ids))
        self.assertIn('"color" "122 179 0"', text)
        self.assertIn("cow001_reference", text)
        self.assertIn("tp3_switch", text)

        group_at = text.index("\n    group\n")
        self.assertLess(text.index("\n    solid\n"), group_at)
        self.assertLess(group_at, text.index("}entity"))

        all_ids = [int(n) for n in re.findall(r'"id" "(\d+)"', text)]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        numbered = sorted(n for n in all_ids if n != 1)
        self.assertEqual(numbered, list(range(1001, 1001 + len(numbered))))
        for gid in block_ids:
            self.assertIn(int(gid), numbered)

        # Height on the floor fails the strict lookup. Scatter's sector id still groups.
        buried = _prop((10, 10, -50), TREE_A)
        self.assertIsNone(vmfpy.scatter_bucket(buried))
        buried["sector_id"] = "0x0x0"
        self.assertEqual(vmfpy.scatter_bucket(buried), ("0x0x0", 0, 0, "trees"))

        saved = cfg.CFG["prop_group_categories"]
        cfg.CFG["prop_group_categories"] = {"trees": ["tree_pine"], "rocks": ["rock"]}
        self.assertEqual(vmfpy.scatter_bucket(low_a)[3], "trees")
        self.assertEqual(vmfpy.scatter_bucket(rock_a)[3], "rocks")
        self.assertIsNone(vmfpy.scatter_bucket(cow))
        cfg.CFG["prop_group_subdivisions"] = 1
        self.assertEqual(vmfpy.scatter_bucket(low_a), vmfpy.scatter_bucket(cell_a))
        cfg.CFG["prop_group_categories"] = saved


if __name__ == "__main__":
    unittest.main()
