"""Hidden track stays in the file, and imported props keep their visgroups."""

import os
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

from railmancer import cfg, joincheck, lines, parser, vmfparse, vmfpy
from railmancer.consolidate_straights import rebuild_track_lines

# Other suites replace this and leave the replacement in place.
_WRITE_BEZIER = lines.write_bezier_points

STRAIGHT = "models/trakpak3_rsg/straights/s0384_0fw_0pg_+0384x00000x0000.mdl"


def _quiet(fn, *args, **kwargs):
    with redirect_stdout(StringIO()):
        return fn(*args, **kwargs)


def _entity(ent_id, origin, editor, wrapper=None):
    body = (
        "entity\n"
        "{\n"
        f'\t"id" "{ent_id}"\n'
        '\t"classname" "prop_static"\n'
        f'\t"model" "{STRAIGHT}"\n'
        f'\t"origin" "{origin}"\n'
        '\t"angles" "0 0 0"\n'
        '\t"skin" "0"\n'
        "\teditor\n"
        "\t{\n"
        f"{editor}"
        "\t}\n"
        "}\n"
    )
    if wrapper == "hidden":
        return "hidden\n{\n" + body + "}\n"
    return body


def _map(body):
    return (
        "versioninfo\n{\n\t\"editorversion\" \"400\"\n}\n"
        "visgroups\n{\n"
        "\tvisgroup\n\t{\n"
        '\t\t"name" "vancouver to squamish"\n'
        '\t\t"visgroupid" "244"\n'
        '\t\t"color" "1 2 3"\n'
        "\t}\n"
        "\tvisgroup\n\t{\n"
        '\t\t"name" "legacy_23"\n'
        '\t\t"visgroupid" "23"\n'
        '\t\t"color" "4 5 6"\n'
        "\t}\n"
        "\tvisgroup\n\t{\n"
        '\t\t"name" "lillooet"\n'
        '\t\t"visgroupid" "9"\n'
        '\t\t"color" "7 8 9"\n'
        "\t}\n"
        "}\n"
        "world\n{\n\t\"id\" \"1\"\n\t\"classname\" \"worldspawn\"\n"
        '\t"skyname" "sky_test"\n}\n'
        f"{body}"
        "cameras\n{\n\t\"activecamera\" \"-1\"\n}\n"
    )


def _import(text):
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, "in.vmf")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    _quiet(parser.import_track, path)
    return _quiet(vmfpy.assemble_vmf)


def _entities(text):
    blocks = vmfparse.parse_blocks(text)
    found = []
    for index, block in enumerate(blocks):
        if block.name != "entity" or block.close_brace < 0:
            continue
        body = text[block.start : block.close_brace + 1]
        keys = vmfparse.read_keys(body)
        found.append((index, block, keys, blocks))
    return found


class HiddenPredicateTests(unittest.TestCase):

    def _keys_for(self, text, ent_id):
        blocks = vmfparse.parse_blocks(text)
        for index, block in enumerate(blocks):
            if block.name != "entity" or block.close_brace < 0:
                continue
            body = text[block.start : block.close_brace + 1]
            keys = vmfparse.read_keys(body)
            if keys.get("id") == ent_id:
                return blocks, index, keys
        self.fail(ent_id)

    def test_each_mark_hides_the_entity(self):
        text = _map(
            _entity("10", "0 0 0", '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "1"\n', "hidden")
            + _entity(
                "11",
                "10 0 0",
                '\t\t"visgroupshown" "0"\n\t\t"visgroupautoshown" "1"\n',
            )
            + _entity(
                "12",
                "20 0 0",
                '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "0"\n',
            )
            + _entity(
                "13",
                "30 0 0",
                '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "1"\n'
                '\t\t"visgroupid" "244"\n',
            )
        )
        for ent_id, hidden in (("10", True), ("11", True), ("12", True), ("13", False)):
            blocks, index, keys = self._keys_for(text, ent_id)
            self.assertEqual(
                vmfparse.entity_is_hidden(blocks, index, keys), hidden, ent_id
            )
        # The sun check stays wrapper-only. shown 0 is not a wrapper.
        blocks, shown_index, _keys = self._keys_for(text, "11")
        self.assertFalse(vmfparse.in_hidden_wrapper(blocks, shown_index))
        blocks, wrapped_index, _keys = self._keys_for(text, "10")
        self.assertTrue(vmfparse.in_hidden_wrapper(blocks, wrapped_index))


class HiddenImportTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):
        self._entities = list(vmfpy.Entities)
        self._brushes = list(vmfpy.Brushes)
        self._brush_entities = list(vmfpy.Brush_Entites)
        self._beziers = list(lines.Beziers)
        vmfpy.Entities.clear()
        vmfpy.Brushes.clear()
        vmfpy.Brush_Entites.clear()
        vmfpy.clear_base_map()
        lines.write_bezier_points = _WRITE_BEZIER
        lines.Beziers = []

    def tearDown(self):
        vmfpy.Entities[:] = self._entities
        vmfpy.Brushes[:] = self._brushes
        vmfpy.Brush_Entites[:] = self._brush_entities
        vmfpy.clear_base_map()
        lines.Beziers[:] = self._beziers

    def test_hidden_props_pass_through_and_visgroups_stay(self):
        text = _map(
            _entity("10", "0 0 0", '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "1"\n', "hidden")
            + _entity(
                "11",
                "100 0 0",
                '\t\t"visgroupshown" "0"\n\t\t"visgroupautoshown" "1"\n'
                '\t\t"visgroupid" "9"\n',
            )
            + _entity(
                "12",
                "200 0 0",
                '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "0"\n',
            )
            + _entity(
                "13",
                "300 0 0",
                '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "1"\n'
                '\t\t"visgroupid" "244"\n'
                '\t\t"visgroupid" "9"\n',
            )
            + _entity(
                "14",
                "400 0 0",
                '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "1"\n'
                '\t\t"visgroupid" "23"\n',
            )
        )
        output = _import(text)
        blocks = vmfparse.parse_blocks(output)

        def own(ent_id):
            for index, block in enumerate(blocks):
                if block.name != "entity" or block.close_brace < 0:
                    continue
                body = output[block.start : block.close_brace + 1]
                keys = vmfparse.read_keys(body)
                if keys.get("id") == ent_id:
                    return index, keys, body
            return None

        for ent_id, origin in (("10", "0 0 0"), ("11", "100 0 0"), ("12", "200 0 0")):
            found = own(ent_id)
            self.assertIsNotNone(found, ent_id)
            index, keys, body = found
            self.assertTrue(vmfparse.entity_is_hidden(blocks, index, keys), ent_id)
            self.assertEqual(keys.get("origin"), origin)
            self.assertIn(STRAIGHT, body)
        straight_origins = [
            keys.get("origin")
            for _index, _block, keys, _blocks in _entities(output)
            if keys.get("model") == STRAIGHT
        ]
        self.assertNotIn("0.0 0.0 0.0", straight_origins)
        self.assertNotIn("100.0 0.0 0.0", straight_origins)
        self.assertNotIn("200.0 0.0 0.0", straight_origins)

        # One curve per visible prop. The three hidden props add none.
        self.assertEqual(len(lines.Beziers), 2)
        self.assertTrue(all(bezier.source == lines.SOURCE_HANDMADE for bezier in lines.Beziers))

        kept = [item for item in _entities(output) if item[2].get("id") not in {"10", "11", "12", "1"}]
        rebuilt = [
            item for item in kept
            if item[2].get("model") == STRAIGHT and item[2].get("origin", "").startswith("300")
        ]
        self.assertEqual(len(rebuilt), 1)
        self.assertEqual(rebuilt[0][2]["visgroupids"], ["244", "9"])
        legacy = [
            item for item in kept
            if item[2].get("model") == STRAIGHT and item[2].get("origin", "").startswith("400")
        ]
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0][2]["visgroupids"], ["23"])

        records = []
        for block in blocks:
            if block.name != "visgroup" or block.close_brace < 0:
                continue
            body = output[block.open_brace : block.close_brace]
            name = vmfparse.read_keys(body).get("name")
            vis_id = vmfparse.read_keys(body).get("visgroupid")
            records.append((name, vis_id))
        new_track = [vis_id for name, vis_id in records if name == "New Track"]
        old_track = [vis_id for name, vis_id in records if name == "Old Track"]
        self.assertEqual(len(new_track), 1)
        self.assertEqual(len(old_track), 1)
        self.assertNotEqual(new_track[0], "23")
        self.assertNotIn(old_track[0], legacy[0][2]["visgroupids"])
        self.assertNotIn(old_track[0], rebuilt[0][2]["visgroupids"])

        # In memory the file's 23 is still 23, so a later rebuild calls it trackhammer.
        imported = [ent for ent in vmfpy.Entities if ent.get("mdl") == STRAIGHT]
        by_x = sorted(imported, key=lambda ent: ent["pos"][0])
        self.assertEqual(by_x[0]["visgroups"], ["244", "9"])
        self.assertEqual(by_x[1]["visgroup"], "23")
        rebuild_track_lines(vmfpy.Entities)
        sources = [bezier.source for bezier in lines.Beziers]
        self.assertEqual(sources, [lines.SOURCE_HANDMADE, lines.SOURCE_TRACKHAMMER])

    def test_joincheck_skips_hidden_track(self):
        text = _map(
            _entity(
                "13",
                "300 0 0",
                '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "1"\n'
                '\t\t"visgroupid" "244"\n',
            )
            + _entity("10", "0 0 0", '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "1"\n', "hidden")
            + _entity(
                "11",
                "100 0 0",
                '\t\t"visgroupshown" "0"\n\t\t"visgroupautoshown" "1"\n',
            )
            + _entity(
                "12",
                "200 0 0",
                '\t\t"visgroupshown" "1"\n\t\t"visgroupautoshown" "0"\n',
            )
        )
        props = joincheck.parse_vmf_track_props(text)
        self.assertEqual(len(props), 1)
        self.assertEqual(props[0]["pos"], [300.0, 0.0, 0.0])
        self.assertEqual(props[0]["visgroups"], ["244"])
