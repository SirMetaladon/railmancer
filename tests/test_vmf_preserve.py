"""The input VMF is the base document. Railmancer is appended to it.

A fresh write (no import, or import of "") still builds Railmancer's own
header. These tests use a small synthetic map with the same kinds of
blocks as Isaiah's Hammer++ file: header groups, a world solid inside
hidden, visgroupshown 0, a func_detail, a light_environment, trakpak
props, and cameras/cordons.
"""

import copy
import os
import re
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import mock_open, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, lines, parser, sectors, track, vmfparse, vmfpy

# Other suites replace vmfpy.add_entity and leave the replacement in place.
_ADD_ENTITY = vmfpy.add_entity

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "preserve_input.vmf")
STRAIGHT = "models/trakpak3_rsg/straights/s0384_0fw_0pg_+0384x00000x0000.mdl"
SWITCH = (
    "models/trakpak3_rsg/switches/sidings/"
    "p0fw_left_minr2048_+0768x00000_+1536x-0192_mn.mdl"
)
BUMPER = "models/trakpak3_rsg/bumpers/bumper_stop.mdl"
DIAMOND = "models/trakpak3_rsg/diamonds/d0fw_1lt.mdl"


def _quiet(fn, *args, **kwargs):
    with redirect_stdout(StringIO()):
        return fn(*args, **kwargs)


def _block_text(text, block):
    return text[vmfparse.line_start(text, block.start) : block.close_brace + 1]


def _own_id(text, block):
    body = text[block.open_brace : block.close_brace + 1]
    # Stop before a nested block so a brush entity's solid id is not its own.
    nested = re.search(r"\n[ \t]*(solid|editor|side|hidden)\b", body)
    head = body[: nested.start()] if nested else body
    match = re.search(r'"id"\s+"(\d+)"', head)
    return match.group(1) if match else None


def _blocks_named(text, name):
    return [block for block in vmfparse.parse_blocks(text) if block.name == name]


def _entity_by_id(text, ent_id):
    for block in _blocks_named(text, "entity"):
        if _own_id(text, block) == str(ent_id):
            return _block_text(text, block)
    return None


def _solid_by_id(text, solid_id):
    for block in _blocks_named(text, "solid"):
        if _own_id(text, block) == str(solid_id):
            return _block_text(text, block)
    return None


def _vis_records(text):
    blocks = vmfparse.parse_blocks(text)
    records = []
    for index, block in enumerate(blocks):
        if block.name != "visgroup" or block.close_brace < 0:
            continue
        body = text[block.open_brace : block.close_brace]
        name = re.search(r'"name"\s+"([^"]*)"', body).group(1)
        vis_id = re.search(r'"visgroupid"\s+"(\d+)"', body).group(1)
        parent = None
        cursor = block.parent
        while cursor is not None:
            if blocks[cursor].name == "visgroup":
                parent_body = text[blocks[cursor].open_brace : blocks[cursor].close_brace]
                parent = re.search(r'"name"\s+"([^"]*)"', parent_body).group(1)
                break
            cursor = blocks[cursor].parent
        records.append((name, vis_id, parent))
    return records


def _record(records, name, parent):
    matches = [item for item in records if item[0] == name and item[2] == parent]
    return matches


def _strip_original(text, original_id):
    return re.sub(rf'[ \t]*"visgroupid" "{original_id}"\n', "", text)


def _top_block(text, name):
    for block in vmfparse.parse_blocks(text):
        if block.name == name and block.parent is None:
            return _block_text(text, block)
    return None


def _ancestor_named(blocks, index, name):
    current = blocks[index].parent
    while current is not None:
        if blocks[current].name == name:
            return True
        current = blocks[current].parent
    return False


class PreserveVmfTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))
        with open(FIXTURE, "r", encoding="utf-8", newline="") as handle:
            cls.fixture = handle.read()

    def setUp(self):
        self._entities = list(vmfpy.Entities)
        self._brushes = list(vmfpy.Brushes)
        self._brush_entities = list(vmfpy.Brush_Entites)
        self._beziers = list(lines.Beziers)
        self._sampled = list(lines.sampled_points)
        self._staged = list(lines.staged_points)
        self._straights = copy.deepcopy(track.track_straight_cache)
        self._lever = parser.lever_id_incrementor
        self._sectors = copy.deepcopy(sectors.Sectors)
        self._lookup = copy.deepcopy(sectors.sector_lookup_grid)
        self._add_entity = vmfpy.add_entity
        vmfpy.add_entity = _ADD_ENTITY
        vmfpy.Entities.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Entites.clear()
        vmfpy.clear_base_map()
        lines.Beziers = []
        lines.sampled_points = []
        lines.staged_points = []

    def tearDown(self):
        vmfpy.Entities[:] = self._entities
        vmfpy.Brushes[:] = self._brushes
        vmfpy.Brush_Entites[:] = self._brush_entities
        vmfpy.clear_base_map()
        lines.Beziers[:] = self._beziers
        lines.sampled_points[:] = self._sampled
        lines.staged_points[:] = self._staged
        track.track_straight_cache.clear()
        track.track_straight_cache.update(self._straights)
        parser.lever_id_incrementor = self._lever
        sectors.Sectors.clear()
        sectors.Sectors.update(self._sectors)
        sectors.sector_lookup_grid.clear()
        sectors.sector_lookup_grid.update(self._lookup)
        vmfpy.add_entity = self._add_entity

    def _import(self, text):
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "in.vmf")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        _quiet(parser.import_track, path)
        return path

    def _add_railmancer_objects(self):
        if "0x0x0" not in sectors.Sectors:
            sectors.new_sector(0, 0, 0, 1600)
        vmfpy.add_brush([0, 64, 0, 64, 0, 16, "floor"])
        vmfpy.add_brush(
            [
                0,
                64,
                0,
                64,
                16,
                32,
                "displacement",
                "RAILMANCER_DISP_TEX",
                "\nDISPINFO_MARKER",
            ]
        )
        vmfpy.add_brush(
            [128, 192, 0, 64, 0, 16, "RAILMANCER_BLOCK_TEX", 0, 0, "24"]
        )
        vmfpy.add_entity(
            {
                "pos": (1, 2, 3),
                "mdl": "models/railmancer_new_track.mdl",
                "ang": (0, 0, 0),
                "visgroup": "23",
            }
        )
        vmfpy.add_entity(
            {
                "pos": (10, 10, 100),
                "mdl": "models/railmancer_scatter.mdl",
                "ang": (0, 0, 0),
                "visgroup": "22",
                "grouping": "tree",
                "sector_id": "0x0x0",
            }
        )
        vmfpy.add_brush_entity([0, 32, 0, 32, 0, 32, "viscluster"])

    def _assemble_imported(self, text, add_light=False):
        self._import(text)
        if add_light:
            vmfpy.add_light_environment()
        _quiet(sectors.collapse_quantum_switchstands)
        self._add_railmancer_objects()
        return _quiet(vmfpy.assemble_vmf)

    def test_input_is_kept_and_track_is_replaced(self):
        self.assertIn('"visgroupshown" "0"', self.fixture)
        hidden_before = sum(
            1
            for block in vmfparse.parse_blocks(self.fixture)
            if block.name == "hidden" and block.parent is None
        )
        self.assertEqual(hidden_before, 3)
        shown_zero_before = self.fixture.count('"visgroupshown" "0"')

        output = self._assemble_imported(self.fixture, add_light=True)
        records = _vis_records(output)
        original = _record(records, "Original", None)
        self.assertEqual(len(original), 1)
        original_id = original[0][1]
        rail = _record(records, "Railmancer", None)
        self.assertEqual(len(rail), 1)
        for name in (
            "Scatter",
            "New Track",
            "Blocks",
            "Terrain",
            "Switch Stands",
            "Old Track",
            "Light",
        ):
            child = _record(records, name, "Railmancer")
            self.assertEqual(len(child), 1, name)
            self.assertGreater(int(child[0][1]), 224)

        defined = [item[1] for item in records]
        self.assertEqual(len(defined), len(set(defined)))
        self.assertIn(("groundhints", "187", None), records)
        self.assertIn(("legacy_22", "22", None), records)
        self.assertIn(("legacy_77", "77", None), records)
        self.assertIn(("legacy_224", "224", None), records)
        self.assertNotEqual(_record(records, "Scatter", "Railmancer")[0][1], "22")
        self.assertNotEqual(_record(records, "Old Track", "Railmancer")[0][1], "25")
        self.assertNotEqual(_record(records, "Light", "Railmancer")[0][1], "77")
        self.assertGreater(int(original_id), 224)

        # Header, worldspawn, and the tail are the input's, not Railmancer's.
        self.assertIn("// PRESERVE_MARKER", output)
        for block_name in ("versioninfo", "viewsettings", "palette_plus", "cameras", "cordons", "cordon"):
            self.assertEqual(
                _top_block(output, block_name),
                _top_block(self.fixture, block_name),
                block_name,
            )
        self.assertIn('"editorbuild" "4242"', output)
        self.assertIn('"color0" "9 8 7"', output)
        self.assertIn('"nGridSpacing" "64"', output)
        self.assertIn('"name0" "keep_cc"', output)
        self.assertIn('"skyname" "sky_test_keep"', output)
        self.assertIn('"detailmaterial" "detail/keep_me"', output)
        self.assertNotIn("sky_stormfront_01", output)
        self.assertIn('"activecamera" "7"', output)
        self.assertIn('"position" "[1 2 3]"', output)
        self.assertIn('"mins" "(0 0 0)"', output)
        self.assertIn('"maxs" "(64 64 64)"', output)
        legacy = re.search(
            r'visgroup\s*\{\s*"name" "legacy_22".*?"color" "11 22 33"\s*\}',
            self.fixture,
            re.DOTALL,
        ).group(0)
        self.assertIn(legacy, output)

        # Untouched objects match once the Original line is ignored.
        for ent_id in ("200", "201", "210", "220", "221", "230", "250", "260", "280", "320", "321"):
            before = _entity_by_id(self.fixture, ent_id)
            after = _entity_by_id(output, ent_id)
            self.assertIsNotNone(before, ent_id)
            self.assertIsNotNone(after, ent_id)
            self.assertEqual(_strip_original(after, original_id), before, ent_id)
            self.assertIn(f'"visgroupid" "{original_id}"', after)

        for solid_id in ("100", "110", "120", "211", "9000"):
            before = _solid_by_id(self.fixture, solid_id)
            after = _solid_by_id(output, solid_id)
            self.assertEqual(_strip_original(after, original_id), before, solid_id)
            self.assertIn(f'"visgroupid" "{original_id}"', after)

        # No editor on the player start: one is created so it can join Original.
        player = _entity_by_id(output, "240")
        self.assertIn('"classname" "info_player_start"', player)
        self.assertIn(f'"visgroupid" "{original_id}"', player)
        self.assertIn('"visgroupshown" "1"', player)
        self.assertNotIn("editor", _entity_by_id(self.fixture, "240"))

        # Ground hints stay in their group and were still sampled.
        ground = _solid_by_id(output, "100")
        self.assertIn('"visgroupid" "187"', ground)
        self.assertIn("GROUND_HINT_TEX", ground)
        self.assertTrue(lines.staged_points)

        # visgroupshown 0 is not flipped, and hidden wrappers stay hidden.
        self.assertEqual(output.count('"visgroupshown" "0"'), shown_zero_before)
        self.assertIn('"targetname" "keep_unshown"', output)
        blocks = vmfparse.parse_blocks(output)
        top_hidden = [
            block for block in blocks if block.name == "hidden" and block.parent is None
        ]
        # Hidden track is not consumed, so its wrapper is not swallowed.
        self.assertEqual(len(top_hidden), 3)
        world_hidden = [
            block
            for index, block in enumerate(blocks)
            if block.name == "solid"
            and _own_id(output, block) == "110"
            and _ancestor_named(blocks, index, "hidden")
        ]
        self.assertEqual(len(world_hidden), 1)
        self.assertIn("HIDDEN_SOLID", output)
        self.assertIn("dispinfo", _solid_by_id(output, "9000"))
        self.assertIn('"power" "3"', _solid_by_id(output, "9000"))

        sibling = _entity_by_id(output, "301")
        self.assertIn('"targetname" "keep_sibling"', sibling)
        sibling_index = next(
            index
            for index, block in enumerate(blocks)
            if block.name == "entity" and _own_id(output, block) == "301"
        )
        self.assertTrue(_ancestor_named(blocks, sibling_index, "hidden"))
        hidden_keep = next(
            index
            for index, block in enumerate(blocks)
            if block.name == "entity" and _own_id(output, block) == "330"
        )
        self.assertTrue(_ancestor_named(blocks, hidden_keep, "hidden"))
        self.assertIn('"visgroupshown" "0"', _entity_by_id(output, "330"))

        # The visible switch is replaced. Hidden straights stay in their wrappers.
        self.assertIsNone(_entity_by_id(output, "310"))
        for kept in ("300", "302"):
            before = _entity_by_id(self.fixture, kept)
            after = _entity_by_id(output, kept)
            self.assertIsNotNone(after, kept)
            self.assertEqual(_strip_original(after, original_id), before, kept)
            self.assertIn(f'"visgroupid" "{original_id}"', after)
            kept_index = next(
                index
                for index, block in enumerate(blocks)
                if block.name == "entity" and _own_id(output, block) == kept
            )
            self.assertTrue(_ancestor_named(blocks, kept_index, "hidden"), kept)
        self.assertEqual(output.count(f'"model" "{STRAIGHT}"'), 2)
        self.assertEqual(output.count(f'"model" "{SWITCH}"'), 1)
        self.assertIn(BUMPER, output)
        self.assertIn(DIAMOND, output)
        self.assertIsNotNone(_entity_by_id(output, "320"))
        self.assertIsNotNone(_entity_by_id(output, "321"))

        old_track = _record(records, "Old Track", "Railmancer")[0][1]
        switch_group = _record(records, "Switch Stands", "Railmancer")[0][1]
        switches = [
            _block_text(output, block)
            for block in blocks
            if block.name == "entity" and '"classname" "tp3_switch"' in _block_text(output, block)
        ]
        self.assertEqual(len(switches), 1)
        # The fixture switch had no visgroup. Import does not stamp Old Track.
        self.assertNotIn("visgroupid", switches[0])
        self.assertNotIn(f'"visgroupid" "{old_track}"', switches[0])
        self.assertNotIn(f'"visgroupid" "{original_id}"', switches[0])
        stands = [
            _block_text(output, block)
            for block in blocks
            if block.name == "entity"
            and "tp3_switch_lever_anim" in _block_text(output, block)
        ]
        self.assertEqual(len(stands), 1)
        self.assertIn(f'"visgroupid" "{switch_group}"', stands[0])
        self.assertNotEqual(switch_group, "27")
        straights = [
            _block_text(output, block)
            for block in blocks
            if block.name == "entity" and STRAIGHT in _block_text(output, block)
        ]
        self.assertEqual(len(straights), 2)
        for straight in straights:
            self.assertNotIn(f'"visgroupid" "{old_track}"', straight)
            self.assertIn(f'"visgroupid" "{original_id}"', straight)

        # Isaiah's visgroup 22 is not rewritten. Scatter is a new id.
        kept = _entity_by_id(output, "200")
        self.assertIn('"visgroupid" "22"', kept)
        self.assertIn('"visgroupid" "9"', kept)
        scatter_id = _record(records, "Scatter", "Railmancer")[0][1]
        self.assertNotIn(f'"visgroupid" "{scatter_id}"', kept)

        new_track = _record(records, "New Track", "Railmancer")[0][1]
        blocks_id = _record(records, "Blocks", "Railmancer")[0][1]
        terrain_id = _record(records, "Terrain", "Railmancer")[0][1]
        new_prop = next(
            _block_text(output, block)
            for block in blocks
            if block.name == "entity" and "railmancer_new_track" in _block_text(output, block)
        )
        self.assertIn(f'"visgroupid" "{new_track}"', new_prop)
        self.assertNotIn(f'"visgroupid" "{original_id}"', new_prop)
        scatter_prop = next(
            _block_text(output, block)
            for block in blocks
            if block.name == "entity" and "railmancer_scatter" in _block_text(output, block)
        )
        self.assertIn(f'"visgroupid" "{scatter_id}"', scatter_prop)
        self.assertIn('"groupid" "', scatter_prop)
        self.assertNotIn(f'"visgroupid" "{original_id}"', scatter_prop)

        block_solid = next(
            _block_text(output, block)
            for block in blocks
            if block.name == "solid" and "RAILMANCER_BLOCK_TEX" in _block_text(output, block)
        )
        self.assertIn(f'"visgroupid" "{blocks_id}"', block_solid)
        self.assertNotIn(f'"visgroupid" "{original_id}"', block_solid)
        disp = next(
            _block_text(output, block)
            for block in blocks
            if block.name == "solid" and "DISPINFO_MARKER" in _block_text(output, block)
        )
        self.assertIn("RAILMANCER_DISP_TEX", disp)
        self.assertIn(f'"visgroupid" "{terrain_id}"', disp)
        self.assertNotIn(f'"visgroupid" "{original_id}"', disp)
        self.assertIn("func_viscluster", output)
        self.assertIn('"classname" "func_detail"', output)
        self.assertNotIn("DETAIL_BRUSH", "\n".join(
            brush for brush in vmfparse.split_vmf_text(output).Brushes
        ))

        ids = [int(value) for value in re.findall(r'"id"\s+"(\d+)"', output)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids.count(9000), 1)
        for solid in (block_solid, disp):
            for value in re.findall(r'"id"\s+"(\d+)"', solid):
                self.assertGreater(int(value), 9000)
        group_ids = [
            int(value)
            for value in re.findall(r'\n    group\n    \{\n        "id" "(\d+)"', output)
        ]
        self.assertEqual(len(group_ids), 1)
        self.assertGreaterEqual(group_ids[0], vmfpy.GROUP_ID_BASE)
        self.assertNotIn(group_ids[0], ids[: ids.index(9000) + 1])
        self.assertTrue(set(group_ids).isdisjoint(set(ids) - set(group_ids)))

        # The input already has a visible sun, so Railmancer's is not added.
        lights = [
            _block_text(output, block)
            for block in blocks
            if block.name == "entity"
            and '"classname" "light_environment"' in _block_text(output, block)
        ]
        self.assertEqual(len(lights), 1)
        self.assertIn('"id" "280"', lights[0])
        self.assertIn('"pitch" "-15"', lights[0])
        self.assertNotIn('"pitch" "-40"', output)

        # The same text is what write_to_vmf saves, and vmfparse can read it.
        with patch("railmancer.vmfpy.os.makedirs"), patch("builtins.open", mock_open()) as opened:
            _quiet(vmfpy.write_to_vmf, "switchstands_output.vmf")
        written = opened().write.call_args[0][0]
        self.assertEqual(written, output)
        with tempfile.TemporaryDirectory() as directory:
            out_path = os.path.join(directory, "out.vmf")
            with open(out_path, "w", encoding="utf-8", newline="") as handle:
                handle.write(output)
            sections = vmfparse.split_vmf(out_path)
        self.assertIn("sky_test_keep", sections.Start)
        self.assertTrue(any("HIDDEN_SOLID" in brush for brush in sections.Brushes))
        self.assertTrue(any("GROUND_HINT_TEX" in brush for brush in sections.Brushes))
        self.assertTrue(any("func_detail" in entity for entity in sections.Entities))
        self.assertTrue(
            any(entity.lstrip().startswith("hidden") and "keep_hidden" in entity for entity in sections.Entities)
        )
        self.assertIn('"activecamera" "7"', sections.End)
        self.assertIn("cordon", sections.End)

    def test_light_environment_rules(self):
        hidden = self._wrap_light(self.fixture)
        output = self._assemble_imported(hidden, add_light=True)
        lights = self._lights(output)
        self.assertEqual(len(lights), 2)
        pitches = [light for light in lights if '"pitch" "-15"' in light]
        added = [light for light in lights if '"pitch" "-40"' in light]
        self.assertEqual(len(pitches), 1)
        self.assertEqual(len(added), 1)
        blocks = vmfparse.parse_blocks(output)
        old_index = next(
            index
            for index, block in enumerate(blocks)
            if block.name == "entity" and '"pitch" "-15"' in _block_text(output, block)
        )
        new_index = next(
            index
            for index, block in enumerate(blocks)
            if block.name == "entity" and '"pitch" "-40"' in _block_text(output, block)
        )
        self.assertTrue(_ancestor_named(blocks, old_index, "hidden"))
        self.assertFalse(_ancestor_named(blocks, new_index, "hidden"))

        unshown = self.fixture.replace(
            '"classname" "light_environment"',
            '"classname" "light_environment"\n\t"targetname" "dim_sun"',
            1,
        )
        unshown = unshown.replace(
            '"_light" "9 8 7 100"\n\t"pitch" "-15"\n\t"origin" "5 6 7"\n\teditor\n\t{\n\t\t"color" "255 255 0"\n\t\t"visgroupshown" "1"',
            '"_light" "9 8 7 100"\n\t"pitch" "-15"\n\t"origin" "5 6 7"\n\teditor\n\t{\n\t\t"color" "255 255 0"\n\t\t"visgroupshown" "0"',
            1,
        )
        vmfpy.Entities.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Entites.clear()
        vmfpy.clear_base_map()
        lines.staged_points.clear()
        output = self._assemble_imported(unshown, add_light=True)
        lights = self._lights(output)
        self.assertEqual(len(lights), 1)
        self.assertIn('"visgroupshown" "0"', lights[0])
        self.assertIn('"pitch" "-15"', lights[0])

        removed = self._delete_entity(self.fixture, "280")
        vmfpy.Entities.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Entites.clear()
        vmfpy.clear_base_map()
        lines.staged_points.clear()
        output = self._assemble_imported(removed, add_light=True)
        lights = self._lights(output)
        self.assertEqual(len(lights), 1)
        self.assertIn('"pitch" "-40"', lights[0])
        self.assertIsNone(_entity_by_id(output, "280"))

    def test_empty_import_path_writes_a_fresh_file(self):
        vmfpy.set_base_map(self.fixture, [])
        self.assertIsNotNone(vmfpy.base_map)
        returned = parser.import_track("")
        self.assertEqual(returned, ([], []))
        self.assertIsNone(vmfpy.base_map)
        vmfpy.add_light_environment()
        output = _quiet(vmfpy.assemble_vmf)
        self.assertIn("sky_stormfront_01", output)
        self.assertNotIn("sky_test_keep", output)
        self.assertNotIn('"name" "Original"', output)
        records = _vis_records(output)
        self.assertIn(("Railmancer", vmfpy.VISGROUP_RAILMANCER, None), records)
        self.assertIn(("Scatter", vmfpy.VISGROUP_SCATTER, "Railmancer"), records)
        self.assertIn(("New Track", vmfpy.VISGROUP_NEW_TRACK, "Railmancer"), records)
        self.assertIn(("Blocks", vmfpy.VISGROUP_BLOCKS, "Railmancer"), records)
        self.assertIn(("Terrain", vmfpy.VISGROUP_TERRAIN, "Railmancer"), records)
        self.assertIn(("Switch Stands", vmfpy.VISGROUP_SWITCH_STANDS, "Railmancer"), records)
        self.assertIn(("Markers", vmfpy.VISGROUP_MARKERS, "Railmancer"), records)
        self.assertIn(("Old Track", vmfpy.VISGROUP_OLD_TRACK, "Railmancer"), records)
        self.assertIn(("Light", vmfpy.VISGROUP_LIGHT, "Railmancer"), records)
        self.assertIn('"visgroupid" "77"', output)
        self.assertIn('"pitch" "-40"', output)

    def test_ids_above_an_input_that_already_uses_the_group_range(self):
        text = """versioninfo
{
	"editorversion" "400"
}
world
{
	"id" "1000000005"
	"classname" "worldspawn"
	"skyname" "sky_high"
	solid
	{
		"id" "1000000004"
		side
		{
			"id" "1000000003"
			"material" "KEEP_HIGH"
		}
		editor
		{
			"visgroupshown" "1"
		}
	}
}
cameras
{
	"activecamera" "-1"
}
"""
        self._import(text)
        sectors.new_sector(0, 0, 0, 1600)
        vmfpy.add_entity(
            {
                "pos": (10, 10, 100),
                "mdl": "models/railmancer_scatter.mdl",
                "ang": (0, 0, 0),
                "grouping": "tree",
                "sector_id": "0x0x0",
                "visgroup": "22",
            }
        )
        vmfpy.add_brush([0, 64, 0, 64, 0, 16, "floor"])
        output = _quiet(vmfpy.assemble_vmf)
        ids = [int(value) for value in re.findall(r'"id"\s+"(\d+)"', output)]
        self.assertEqual(len(ids), len(set(ids)))
        group_ids = [
            int(value)
            for value in re.findall(r'\n    group\n    \{\n        "id" "(\d+)"', output)
        ]
        self.assertEqual(group_ids, [1000000006])
        fresh = [value for value in ids if value > 1000000005 and value not in group_ids]
        self.assertTrue(fresh)
        self.assertGreater(min(fresh), max(group_ids))
        self.assertIn("KEEP_HIGH", output)
        self.assertIn("sky_high", output)
        records = _vis_records(output)
        # No visgroups block in the input: one is created, and its ids start at 1.
        self.assertEqual(_record(records, "Railmancer", None)[0][1], "1")
        self.assertEqual(_record(records, "Original", None)[0][1], "9")
        self.assertIn('"visgroupid" "9"', _solid_by_id(output, "1000000004"))

    def _lights(self, text):
        return [
            _block_text(text, block)
            for block in vmfparse.parse_blocks(text)
            if block.name == "entity"
            and '"classname" "light_environment"' in _block_text(text, block)
        ]

    def _wrap_light(self, text):
        blocks = vmfparse.parse_blocks(text)
        for block in blocks:
            if block.name != "entity" or block.parent is not None:
                continue
            if _own_id(text, block) != "280":
                continue
            start = vmfparse.line_start(text, block.start)
            end = block.close_brace + 1
            chunk = text[start:end]
            return text[:start] + "hidden\n{\n" + chunk + "\n}\n" + text[end:]
        raise AssertionError("light entity missing")

    def _delete_entity(self, text, ent_id):
        blocks = vmfparse.parse_blocks(text)
        for block in blocks:
            if block.name == "entity" and _own_id(text, block) == ent_id:
                start = vmfparse.line_start(text, block.start)
                end = block.close_brace + 1
                return text[:start] + text[end:]
        raise AssertionError(ent_id)


if __name__ == "__main__":
    unittest.main()
