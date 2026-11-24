"""Hammer groups for scattered props.

One group per (sector, subsector x, subsector y, grouping), including a
single prop. The id is GROUP_ID_BASE plus that key's sorted rank, so it
stays out of the solid and entity id counter. A prop with no grouping,
and a non-prop, stay loose.
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
CACTUS = "models/props_foliage/cactus01.mdl"


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
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        vmfpy.Entities.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Entites.clear()

    def test_one_group_per_sector_cell_and_grouping(self):
        # Config ships 2. setUp forces 4, which is what the 256-unit cells below use.
        self.assertEqual(self._subs, 2)
        self.assertEqual(cfg.CFG["prop_group_subdivisions"], 4)
        self.assertNotIn("prop_group_categories", cfg.CFG)
        biomes = cfg.CFG["Biomes"]
        self.assertEqual(biomes["hl2_white_forest"]["models"][TREE_A]["grouping"], "tree")
        self.assertEqual(biomes["hl2_white_forest"]["models"][ROCK_A]["grouping"], "rock")
        self.assertEqual(biomes["tf2_alpine_snow"]["models"][TREE_B]["grouping"], "tree")
        self.assertEqual(biomes["tf2_alpine_snow"]["models"][ROCK_B]["grouping"], "rock")
        self.assertNotIn("grouping", biomes["dev_null"]["models"][COW])
        self.assertNotIn("grouping", biomes["tf2_desert_flat"]["models"][CACTUS])

        # 1024 / 4 = 256. Low floor is 0..1600, high floor is 3200..4800.
        sectors.new_sector(0, 0, 0, 1600)
        sectors.new_sector(1, 0, 0, 1600)
        sectors.new_sector(0, 0, 3200, 4800)
        self.assertIn("0x0x0", sectors.Sectors)
        self.assertIn("1x0x0", sectors.Sectors)
        self.assertIn("0x0x200", sectors.Sectors)

        low_a = _prop((10, 10, 100), TREE_A, grouping="tree")
        low_b = _prop((20, 40, 100), TREE_B, grouping="tree")
        cell_a = _prop((300, 10, 100), TREE_A, grouping="tree")
        cell_b = _prop((400, 20, 100), TREE_B, grouping="tree")
        rock_a = _prop((30, 30, 100), ROCK_A, grouping="rock")
        rock_b = _prop((50, 60, 100), ROCK_B, grouping="rock")
        side_a = _prop((1030, 10, 100), TREE_A, grouping="tree")
        side_b = _prop((1100, 20, 100), TREE_B, grouping="tree")
        high_a = _prop((10, 10, 4000), TREE_A, grouping="tree")
        high_b = _prop((20, 40, 4000), TREE_B, grouping="tree")
        lone = _prop((10, 300, 100), TREE_A, grouping="tree")
        cow = _prop((15, 15, 100), COW)
        switch = _prop((12, 12, 100), TREE_A, grouping="tree", classname="tp3_switch")
        outside = _prop((9000, 10, 100), TREE_A, grouping="tree")
        props = [
            low_a, low_b, cell_a, cell_b, rock_a, rock_b,
            side_a, side_b, high_a, high_b, lone, cow, switch, outside,
        ]

        self.assertEqual(vmfpy.scatter_bucket(low_a), ("0x0x0", 0, 0, "tree"))
        self.assertEqual(vmfpy.scatter_bucket(cell_a), ("0x0x0", 1, 0, "tree"))
        self.assertEqual(vmfpy.scatter_bucket(rock_a), ("0x0x0", 0, 0, "rock"))
        self.assertEqual(vmfpy.scatter_bucket(side_a), ("1x0x0", 0, 0, "tree"))
        self.assertEqual(vmfpy.scatter_bucket(high_a), ("0x0x200", 0, 0, "tree"))
        self.assertEqual(vmfpy.scatter_bucket(lone), ("0x0x0", 0, 1, "tree"))
        self.assertIsNone(vmfpy.scatter_bucket(cow))
        self.assertIsNone(vmfpy.scatter_bucket(switch))
        self.assertIsNone(vmfpy.scatter_bucket(outside))

        keys = sorted({vmfpy.scatter_bucket(prop) for prop in props} - {None})
        self.assertEqual(len(keys), 6)
        expected = {
            key: str(vmfpy.GROUP_ID_BASE + index) for index, key in enumerate(keys)
        }

        vmfpy.Entities.extend(props)
        vmfpy.add_brush([0, 128, 0, 128, 0, 16, "floor"])
        with redirect_stdout(StringIO()):
            text = vmfpy.assemble_vmf()

        for prop in props:
            key = vmfpy.scatter_bucket(prop)
            if key is None:
                self.assertNotIn("groupid", prop)
            else:
                self.assertEqual(prop["groupid"], expected[key])

        # Same cell, different grouping. Neighbor sector. Stacked floor. Other cell.
        self.assertNotEqual(low_a["groupid"], rock_a["groupid"])
        self.assertNotEqual(low_a["groupid"], side_a["groupid"])
        self.assertNotEqual(low_a["groupid"], high_a["groupid"])
        self.assertNotEqual(low_a["groupid"], cell_a["groupid"])
        self.assertNotEqual(low_a["groupid"], lone["groupid"])
        self.assertEqual(low_a["groupid"], low_b["groupid"])
        self.assertIn("groupid", lone)

        block_ids = re.findall(r'\n    group\n    \{\n        "id" "(\d+)"', text)
        ref_ids = re.findall(r'"groupid" "(\d+)"', text)
        self.assertEqual(sorted(block_ids), sorted(expected.values()))
        self.assertEqual(sorted(ref_ids), sorted(prop["groupid"] for prop in props if "groupid" in prop))
        self.assertEqual(len(block_ids), 6)
        self.assertEqual(ref_ids.count(lone["groupid"]), 1)
        self.assertIn('"color" "122 179 0"', text)
        self.assertIn("cow001_reference", text)
        self.assertIn("tp3_switch", text)

        group_at = text.index("\n    group\n")
        self.assertLess(text.index("\n    solid\n"), group_at)
        self.assertLess(group_at, text.index("}entity"))

        all_ids = [int(n) for n in re.findall(r'"id" "(\d+)"', text)]
        self.assertEqual(len(all_ids), len(set(all_ids)))
        group_nums = [int(gid) for gid in block_ids]
        self.assertEqual(
            sorted(group_nums),
            list(range(vmfpy.GROUP_ID_BASE, vmfpy.GROUP_ID_BASE + len(group_nums))),
        )
        numbered = sorted(n for n in all_ids if n != 1 and n < vmfpy.GROUP_ID_BASE)
        self.assertEqual(numbered, list(range(1001, 1001 + len(numbered))))
        self.assertTrue(set(group_nums).isdisjoint(numbered))

        buried = _prop((10, 10, -50), TREE_A, grouping="tree")
        self.assertIsNone(vmfpy.scatter_bucket(buried))
        buried["sector_id"] = "0x0x0"
        self.assertEqual(vmfpy.scatter_bucket(buried), ("0x0x0", 0, 0, "tree"))

        cfg.CFG["prop_group_subdivisions"] = 1
        self.assertEqual(vmfpy.scatter_bucket(low_a), vmfpy.scatter_bucket(cell_a))
        self.assertNotEqual(vmfpy.scatter_bucket(low_a), vmfpy.scatter_bucket(high_a))


if __name__ == "__main__":
    unittest.main()
