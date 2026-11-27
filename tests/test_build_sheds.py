"""Automatic build sheds: targets, slots, shell, door, and visgroup import."""

import copy
import os
import re
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, lines, parser, sectors, track, vmfparse, vmfpy
from railmancer.build_sheds import (
    DOOR_H,
    DOOR_TRACK_CLEAR,
    DOOR_W,
    GRASS,
    STACK_GAP,
    SUBFLOOR,
    TRACK_ABOVE_GRASS,
    WALL,
    add_shed,
    build_targets,
    find_slots,
    fit_straights,
    shed_member_spans,
    spawn_box_from_text,
)
from railmancer.straight_catalog import get_catalog

SHED_TRACK = "models/trakpak3_rsg/straights/s0384_0fw_0pg_+0384x00000x0000.mdl"
MAIN_TRACK = "models/trakpak3_rsg/straights/s0128_0fw_0pg_+0128x00000x0000.mdl"


def _quiet(fn, *args, **kwargs):
    with redirect_stdout(StringIO()):
        return fn(*args, **kwargs)


def _materials(brush_list):
    vmfpy.ID = 1000
    text = vmfpy.brush(copy.deepcopy(brush_list))
    return re.findall(r'"material" "([^"]+)"', text)


def _vmf_with_shed_track():
    return f"""versioninfo
{{
    "editorversion" "400"
    "editorbuild" "8868"
    "mapversion" "1"
    "formatversion" "100"
    "prefab" "0"
}}
visgroups
{{
    visgroup
    {{
        "name" "Build Sheds"
        "visgroupid" "55"
        "color" "1 2 3"
        visgroup
        {{
            "name" "nested decoy"
            "visgroupid" "56"
            "color" "0 0 0"
        }}
    }}
    visgroup
    {{
        "name" "Not Sheds"
        "visgroupid" "31"
        "color" "4 5 6"
    }}
}}
world
{{
    "id" "1"
    "classname" "worldspawn"
    "skyname" "sky_test"
    solid
    {{
        "id" "2"
        side
        {{
            "id" "3"
            "plane" "(0 0 0) (64 0 0) (64 64 0)"
            "material" "OLD_SHED_FLOOR"
        }}
        editor
        {{
            "visgroupshown" "1"
            "visgroupid" "55"
        }}
    }}
    solid
    {{
        "id" "4"
        side
        {{
            "id" "5"
            "plane" "(128 128 0) (192 128 0) (192 192 0)"
            "material" "KEEP_FLOOR"
        }}
        editor
        {{
            "visgroupshown" "1"
        }}
    }}
    solid
    {{
        "id" "6"
        side
        {{
            "id" "7"
            "plane" "(0 0 0) (256 0 0) (256 256 16)"
            "material" "SPAWN_FLOOR"
        }}
        editor
        {{
            "visgroupshown" "1"
        }}
    }}
    solid
    {{
        "id" "8"
        side
        {{
            "id" "9"
            "plane" "(0 0 128) (256 0 128) (256 256 144)"
            "material" "SPAWN_CEILING"
        }}
        editor
        {{
            "visgroupshown" "1"
        }}
    }}
    solid
    {{
        "id" "70"
        side
        {{
            "id" "71"
            "plane" "(0 0 0) (16 0 144) (16 256 144)"
            "material" "SPAWN_WALL"
        }}
        editor
        {{
            "visgroupshown" "1"
        }}
    }}
}}
entity
{{
    "id" "10"
    "classname" "prop_static"
    "model" "{SHED_TRACK}"
    "origin" "8000 8000 64"
    "angles" "0 0 0"
    "skin" "0"
    editor
    {{
        "visgroupshown" "1"
        "visgroupid" "55"
    }}
}}
entity
{{
    "id" "11"
    "classname" "prop_static"
    "model" "{MAIN_TRACK}"
    "origin" "0 0 0"
    "angles" "0 0 0"
    "skin" "0"
    editor
    {{
        "visgroupshown" "1"
        "visgroupid" "31"
    }}
}}
entity
{{
    "id" "12"
    "classname" "info_player_start"
    "origin" "100 100 16"
    "angles" "0 90 0"
}}
entity
{{
    "id" "13"
    "classname" "trigger_teleport"
    "target" "build1"
    "spawnflags" "1"
    solid
    {{
        "id" "14"
        side
        {{
            "id" "15"
            "plane" "(0 0 0) (56 0 0) (56 8 112)"
            "material" "TOOLS/TOOLSTRIGGER"
        }}
    }}
}}
entity
{{
    "id" "16"
    "classname" "trigger_teleport"
    "target" "not_a_shed"
    "origin" "0 0 0"
}}
"""


class BuildShedTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):
        self._entities = list(vmfpy.Entities)
        self._brushes = list(vmfpy.Brushes)
        self._brush_entities = list(vmfpy.Brush_Entites)
        self._brush_keys = list(vmfpy.Brush_Group_Keys)
        self._beziers = list(lines.Beziers)
        self._sampled = lines.sampled_points
        self._staged = list(lines.staged_points)
        self._straights = copy.deepcopy(track.track_straight_cache)
        self._sectors = copy.deepcopy(sectors.Sectors)
        self._lookup = copy.deepcopy(sectors.sector_lookup_grid)
        self._base = vmfpy.base_map
        vmfpy.Entities.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Entites.clear()
        vmfpy.Brush_Group_Keys.clear()
        vmfpy.clear_base_map()
        lines.Beziers.clear()
        lines.sampled_points = []
        lines.staged_points.clear()
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()

    def tearDown(self):
        vmfpy.Entities[:] = self._entities
        vmfpy.Brushes[:] = self._brushes
        vmfpy.Brush_Entites[:] = self._brush_entities
        vmfpy.Brush_Group_Keys[:] = self._brush_keys
        vmfpy.base_map = self._base
        lines.Beziers[:] = self._beziers
        lines.sampled_points = self._sampled
        lines.staged_points[:] = self._staged
        track.track_straight_cache.clear()
        track.track_straight_cache.update(self._straights)
        sectors.Sectors.clear()
        sectors.Sectors.update(self._sectors)
        sectors.sector_lookup_grid.clear()
        sectors.sector_lookup_grid.update(self._lookup)

    def test_config_and_targets(self):
        self.assertTrue(cfg.CFG["build_sheds_enabled"])
        self.assertEqual(cfg.CFG["build_shed_height"], 1856)
        self.assertEqual(cfg.CFG["build_shed_track_margin"], 80)
        self.assertEqual(cfg.CFG["build_shed_return_target"], "spawn")
        self.assertEqual(vmfpy.VISGROUP_BUILD_SHEDS, "31")

        chunks = []
        for target in ("build2", "Build1", "BUILD10", "build", "rebuild1"):
            chunks.append(
                "entity\n{\n"
                '"classname" "trigger_teleport"\n'
                f'"target" "{target}"\n'
                "}\n"
            )
        chunks.append(
            "entity\n{\n"
            '"classname" "info_teleport_destination"\n'
            '"targetname" "build4"\n'
            "}\n"
        )
        vmf = (
            "world\n{\n\"id\" \"1\"\n\"classname\" \"worldspawn\"\n}\n"
            + "".join(chunks)
        )
        self.assertEqual(
            build_targets(vmf), ["build1", "build2", "build10"]
        )
        self.assertEqual(build_targets("", explicit=3), ["build1", "build2", "build3"])
        self.assertEqual(
            build_targets("", explicit=["build2", "Build2", "build1", "nope"]),
            ["build1", "build2"],
        )

    def test_slots_stack_and_stay_clear(self):
        size = 3264
        height = 1856
        per_map = 10
        indexes = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4]

        # Spawn owns the whole first column. The next column has a sector
        # through the middle, so the sheds stack in the free band under it.
        sectors.new_sector(-5, -4, 0, 4000)
        spawn = (-16320, -13056, -16320, -13056, -16384, 16320)
        low = find_slots(3, size, height, spawn_box=spawn, sectors_per_map=per_map)
        self.assertEqual(len(low), 3)
        self.assertTrue(all(slot[0] == -16320 and slot[1] == -13056 for slot in low))
        self.assertTrue(all(slot[2] % 16 == 0 for slot in low))
        for slot in low:
            self.assertGreaterEqual(slot[2], -16384)
            self.assertLessEqual(slot[2] + height, 16320)
            self.assertLessEqual(slot[2] + height, -STACK_GAP)
            self.assertLessEqual(abs(slot[0]), 16384)
            self.assertLessEqual(abs(slot[1]), 16384)
        self.assertEqual(low[1][2] - low[0][2], height + STACK_GAP)
        self.assertNotIn(-16320, [slot[1] for slot in low])

        # Every other column is full. The one open column has a floor, and
        # the two sheds stack above it with the buffer between them.
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        for sx in indexes:
            for sy in indexes:
                if (sx, sy) == (-5, -5):
                    sectors.new_sector(sx, sy, -16384, 0)
                else:
                    sectors.new_sector(sx, sy, -16384, 16320)
        stacked = find_slots(2, size, height, sectors_per_map=per_map)
        self.assertEqual(
            stacked,
            [(-16320, -16320, STACK_GAP), (-16320, -16320, STACK_GAP + height + STACK_GAP)],
        )
        for slot in stacked:
            self.assertGreaterEqual(slot[2], STACK_GAP)
            self.assertLessEqual(slot[0] + size, 16384)
            self.assertGreaterEqual(slot[0], -16384)

    def test_straights_use_the_catalog(self):
        catalog = get_catalog()
        one = fit_straights(3264, 80, catalog)
        self.assertEqual([piece.length for piece in one], [3072])
        self.assertEqual(one[0].grade_token, "0pg")
        self.assertEqual(one[0].direction, "0fw")

        for sector_size, lengths in (
            (2048, [1536, 256, 64]),
            (4096, [3072, 768, 64]),
        ):
            pieces = fit_straights(sector_size, 80, catalog)
            self.assertEqual([piece.length for piece in pieces], lengths)
            interior = sector_size - 2 * WALL
            used = sum(lengths)
            self.assertGreaterEqual((interior - used) // 2, 80)
            self.assertTrue(all(catalog.get("0fw", "0pg", length) for length in lengths))

        self.assertEqual(fit_straights(192, 80, catalog), [])

    def test_shell_door_track_and_visgroup(self):
        add_shed("build1", (0, 0, 0), 3264, 1856, 80, "spawn")
        brushes = vmfpy.Brushes
        self.assertEqual(len(brushes), 11)
        for brush in brushes:
            self.assertEqual(brush[9], vmfpy.VISGROUP_BUILD_SHEDS)

        def bounds(brush):
            return tuple(brush[0:6])

        by_bounds = {bounds(brush): brush for brush in brushes}
        subfloor = by_bounds[(0, 3264, 0, 3264, 0, 16)]
        grass = by_bounds[(16, 3248, 16, 3248, 16, 32)]
        south = by_bounds[(0, 3264, 0, 16, 16, 1840)]
        north = by_bounds[(0, 3264, 3248, 3264, 16, 1840)]
        west = by_bounds[(0, 16, 0, 3264, 16, 1840)]
        east = by_bounds[(3248, 3264, 0, 3264, 16, 1840)]
        ceiling = by_bounds[(0, 3264, 0, 3264, 1840, 1856)]
        panel = by_bounds[(1696, 1752, 16, 18, 32, 140)]
        bar = by_bounds[(1696, 1752, 16, 20, 140, 144)]
        self.assertIn((1692, 1696, 16, 18, 32, 140), by_bounds)
        self.assertIn((1752, 1756, 16, 18, 32, 140), by_bounds)

        self.assertEqual(_materials(subfloor), ["TOOLS/TOOLSNODRAW"] * 6)
        grass_mats = _materials(grass)
        self.assertEqual(grass_mats[0], "RAVINE/BLENDDIRTTOGRASS001")
        self.assertEqual(grass_mats[1:], ["TOOLS/TOOLSNODRAW"] * 5)
        south_mats = _materials(south)
        self.assertEqual(south_mats[4], "TOOLS/TOOLSSKYBOX")
        self.assertTrue(all(mat == "TOOLS/TOOLSNODRAW" for i, mat in enumerate(south_mats) if i != 4))
        self.assertEqual(_materials(north)[5], "TOOLS/TOOLSSKYBOX")
        self.assertEqual(_materials(west)[3], "TOOLS/TOOLSSKYBOX")
        self.assertEqual(_materials(east)[2], "TOOLS/TOOLSSKYBOX")
        ceiling_mats = _materials(ceiling)
        self.assertEqual(ceiling_mats[1], "TOOLS/TOOLSSKYBOX")
        self.assertTrue(all(mat == "TOOLS/TOOLSNODRAW" for i, mat in enumerate(ceiling_mats) if i != 1))
        panel_mats = _materials(panel)
        self.assertEqual(panel_mats[4], "METAL/OFFICEDOOR002")
        self.assertEqual(panel_mats[5], "TOOLS/TOOLSNODRAW")
        self.assertTrue(all(mat == "CONCRETE/COMPUTERWALL007" for mat in panel_mats[:4]))
        self.assertEqual(_materials(bar)[4], "CONCRETE/COMPUTERWALL007")

        self.assertEqual(len(vmfpy.Brush_Entites), 1)
        trigger = vmfpy.Brush_Entites[0]
        self.assertEqual(trigger["bounds"], (1696, 1752, 20, 28, 32, 144))
        self.assertEqual(trigger["spawnflags"], "1")
        self.assertEqual(trigger["StartDisabled"], "0")
        self.assertEqual(trigger["target"], "spawn")
        self.assertEqual(trigger["visgroup"], "31")
        self.assertEqual(trigger["bounds"][3] - trigger["bounds"][2], 8)
        self.assertEqual(trigger["bounds"][5] - trigger["bounds"][4], DOOR_H)
        self.assertEqual(trigger["bounds"][1] - trigger["bounds"][0], DOOR_W)

        dest = next(
            ent for ent in vmfpy.Entities if ent["classname"] == "info_teleport_destination"
        )
        track_prop = next(ent for ent in vmfpy.Entities if ent["classname"] == "prop_static")
        self.assertEqual(dest["targetname"], "build1")
        self.assertEqual(dest["pos"], (1724, 92, 32 + 16))
        self.assertEqual(dest["ang"], (0, 90, 0))
        self.assertEqual(dest["visgroup"], "31")
        # 64 past the trigger's inner face, beside the rail rather than on it.
        self.assertEqual(dest["pos"][1] - trigger["bounds"][3], 64)
        self.assertGreaterEqual(dest["pos"][0] - 1632, DOOR_TRACK_CLEAR)
        tx0, tx1, ty0, ty1, tz0, tz1 = trigger["bounds"]
        dx, dy, dz = dest["pos"]
        self.assertFalse(tx0 <= dx <= tx1 and ty0 <= dy <= ty1 and tz0 <= dz <= tz1)

        self.assertIn("s3072_0fw_0pg", track_prop["mdl"])
        self.assertEqual(track_prop["pos"], (1632, 16 + 80, SUBFLOOR + GRASS + TRACK_ABOVE_GRASS))
        self.assertEqual(track_prop["ang"], (0, -90, 0))
        self.assertEqual(track_prop["visgroup"], "31")
        self.assertEqual(track_prop["pos"][1] - 16, 80)
        self.assertEqual((3264 - 16) - (track_prop["pos"][1] + 3072), 80)

        text = _quiet(vmfpy.assemble_vmf)
        self.assertIn('"name" "Build Sheds"', text)
        self.assertIn('"visgroupid" "31"', text)
        self.assertIn('"classname" "trigger_teleport"', text)
        self.assertIn('"spawnflags" "1"', text)
        self.assertIn('"target" "spawn"', text)
        self.assertIn('"classname" "info_teleport_destination"', text)
        self.assertIn('"targetname" "build1"', text)
        self.assertIn("TOOLS/TOOLSTRIGGER", text)

    def test_add_brush_checks_the_second_z(self):
        vmfpy.add_brush([0, 16, 0, 16, 0, -16385, "floor"])
        self.assertEqual(vmfpy.Brushes, [])
        vmfpy.add_brush([0, 16, 0, 16, 16385, 0, "floor"])
        self.assertEqual(vmfpy.Brushes, [])
        vmfpy.add_brush([0, 16, 0, 16, -16384, -16368, "floor"])
        self.assertEqual(len(vmfpy.Brushes), 1)
        self.assertEqual(vmfpy.Brushes[0][4], -16384)
        self.assertEqual(vmfpy.Brushes[0][5], -16368)

        vmfpy.Brushes.clear()
        vmfpy.Brush_Group_Keys.clear()
        add_shed("build9", (-16320, -16320, -16384), 3264, 1856, 80, "spawn")
        self.assertTrue(any(min(brush[4], brush[5]) == -16384 for brush in vmfpy.Brushes))

    def test_import_ignores_remapped_build_sheds_visgroup(self):
        text = _vmf_with_shed_track()
        self.assertEqual(
            vmfparse.visgroup_ids_named(text, "Build Sheds"), {"55"}
        )
        # The old floor solid and the shed prop, not the nested decoy id.
        self.assertEqual(len(shed_member_spans(text)), 2)
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "in.vmf")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        _quiet(parser.import_track, path)

        models = [ent.get("mdl") for ent in vmfpy.Entities]
        self.assertIn(MAIN_TRACK, models)
        self.assertNotIn(SHED_TRACK, models)
        starts = []
        for bezier in lines.Beziers:
            start = bezier[0]
            starts.append((float(start[0]), float(start[1]), float(start[2])))
        self.assertIn((0.0, 0.0, 0.0), starts)
        self.assertNotIn((8000.0, 8000.0, 64.0), starts)

        _quiet(lines.encode_lines)
        _quiet(sectors.build_fit)
        self.assertNotIn("2x2", sectors.sector_lookup_grid)
        self.assertTrue(sectors.sector_lookup_grid)

        placed = _quiet(build_sheds_apply)
        self.assertEqual(placed, 1)
        output = _quiet(vmfpy.assemble_vmf)
        self.assertNotIn("OLD_SHED_FLOOR", output)
        self.assertNotIn("s0384_0fw_0pg", output)
        self.assertIn("KEEP_FLOOR", output)
        self.assertIn('"targetname" "build1"', output)
        self.assertIn(MAIN_TRACK, output)
        self.assertIn('"name" "Build Sheds"', output)

    def test_spawn_box_follows_the_room_not_a_huge_brush(self):
        text = _vmf_with_shed_track()
        # A landscape-sized solid must not become the spawn.
        text = text.replace(
            '"skyname" "sky_test"',
            '"skyname" "sky_test"\n'
            "solid\n{\n\"id\" \"90\"\nside\n{\n\"id\" \"91\"\n"
            '"plane" "(0 0 -16) (20000 0 -16) (20000 64 -16)"\n'
            '"material" "HUGE"\n}\n}\n',
        )
        box = spawn_box_from_text(text, 3264)
        self.assertIsNotNone(box)
        self.assertLessEqual(box[0], 0)
        self.assertGreaterEqual(box[1], 256)
        self.assertLessEqual(box[4], 0)
        self.assertGreaterEqual(box[5], 128)
        self.assertLess(box[1], 3264)


def build_sheds_apply():
    from railmancer.build_sheds import apply

    return apply()


if __name__ == "__main__":
    unittest.main()
