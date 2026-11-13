"""Consolidation of fragmented straight props.

Builds synthetic chains from the committed TrakPak3 manifest (no .mdl bytes),
merges them, and checks that the open endpoints stay exactly where they were.
Also round-trips a tiny VMF through consolidate_vmf_text.
"""

import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import joincheck, tools, track
from railmancer.consolidate_straights import (
    consolidate_props,
    consolidate_vmf_text,
)
from railmancer.straight_catalog import ALLOWED_LENGTHS, get_catalog
from railmancer.trakpak_manifest import install_manifest_library


def _open_ends(props):
    library, unknown = joincheck.library_from_prop_names(props)
    assert not unknown, unknown
    counts, _ = joincheck.tally_endpoints(props, library)
    return {key for key, count in counts.items() if count == 1}, library


def _make_flat_chain(lengths, origin=(0, 0, 0), yaw=-90, direction="0fw"):
    catalog = get_catalog()
    props = []
    pos = list(origin)
    for length in lengths:
        piece = catalog.get(direction, "0pg", length)
        assert piece is not None, (direction, length)
        props.append({"mdl": piece.model, "pos": list(pos), "ang": (0, yaw, 0)})
        rotated = tools.rot_orth(piece.move, yaw)
        pos = [pos[i] + float(rotated[i]) for i in range(3)]
    return props


def _make_graded_chain(specs, origin=(0, 0, 0), yaw=-90, direction="0fw"):
    catalog = get_catalog()
    props = []
    pos = list(origin)
    for length, grade in specs:
        piece = catalog.get(direction, grade, length)
        assert piece is not None, (direction, grade, length)
        props.append({"mdl": piece.model, "pos": list(pos), "ang": (0, yaw, 0)})
        rotated = tools.rot_orth(piece.move, yaw)
        pos = [pos[i] + float(rotated[i]) for i in range(3)]
    return props


def _make_downhill(lengths, grade="312pg", origin=(0, 0, 0), heading=-90):
    catalog = get_catalog()
    props = []
    current = list(origin)
    for length in lengths:
        piece = catalog.get("0fw", grade, length)
        travel = (piece.move[0], piece.move[1], -piece.rise)
        next_pos = [
            current[i] + float(tools.rot_orth(travel, heading)[i]) for i in range(3)
        ]
        props.append(
            {
                "mdl": piece.model,
                "pos": list(next_pos),
                "ang": (0, heading + 180, 0),
            }
        )
        current = next_pos
    return props


def _vmf_from_props(props):
    chunks = ['world\n{\n\t"id" "1"\n\t"classname" "worldspawn"\n}\n']
    for index, prop in enumerate(props, start=2):
        ang = prop["ang"]
        pos = prop["pos"]
        chunks.append(
            "entity\n"
            "{\n"
            f'\t"id" "{index}"\n'
            '\t"classname" "prop_static"\n'
            f'\t"angles" "{ang[0]} {ang[1]} {ang[2]}"\n'
            f'\t"model" "{prop["mdl"]}"\n'
            f'\t"origin" "{pos[0]} {pos[1]} {pos[2]}"\n'
            "}\n"
        )
    chunks.append("cameras\n{\n\t\"activecamera\" \"-1\"\n}\n")
    return "".join(chunks)


class StraightCatalogTests(unittest.TestCase):

    def test_allowed_lengths_match_generator(self):
        self.assertEqual(
            list(ALLOWED_LENGTHS),
            [32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048, 3072, 4096, 6144, 8192],
        )

    def test_grades_baked_for_0fw(self):
        catalog = get_catalog()
        grades = catalog.grades_for("0fw")
        self.assertEqual(grades, ("0pg", "156pg", "234pg", "312pg"))
        self.assertEqual(catalog.grade_info["0fw"]["312pg"].real_grade, 3.12)
        self.assertIn(8192, catalog.lengths_for("0fw", "0pg"))
        self.assertNotIn(32, catalog.lengths_for("0fw", "156pg"))


class ConsolidatePropsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        install_manifest_library()

    def test_flat_fragments_become_one_piece(self):
        props = _make_flat_chain([32, 32, 64])
        before_ends, library = _open_ends(props)
        self.assertEqual(joincheck.audit_props(props, library, allowed_open=before_ends), [])

        out, stats = consolidate_props(props, smooth_grade=False)
        self.assertEqual(stats.straight_before, 3)
        self.assertEqual(stats.straight_after, 1)
        self.assertEqual(len(out), 1)
        self.assertIn("s0128_0fw_0pg_", out[0]["mdl"])

        after_ends, library2 = _open_ends(out)
        self.assertEqual(before_ends, after_ends)
        self.assertEqual(joincheck.audit_props(out, library2, allowed_open=before_ends), [])

    def test_same_grade_merges_without_smooth(self):
        props = _make_graded_chain([(256, "312pg"), (256, "312pg")])
        before_ends, _ = _open_ends(props)
        out, stats = consolidate_props(props, smooth_grade=False)
        self.assertEqual(stats.straight_after, 1)
        self.assertIn("s0512_0fw_312pg_", out[0]["mdl"])
        after_ends, library = _open_ends(out)
        self.assertEqual(before_ends, after_ends)
        self.assertEqual(joincheck.audit_props(out, library, allowed_open=before_ends), [])

    def test_mixed_grades_stay_separate_without_smooth(self):
        props = _make_graded_chain([(256, "312pg"), (256, "0pg")])
        out, stats = consolidate_props(props, smooth_grade=False)
        self.assertEqual(stats.runs_merged, 0)
        self.assertEqual(len(out), 2)

    def test_smooth_grade_mixes_tokens_to_hit_rise(self):
        props = _make_graded_chain([(256, "312pg"), (256, "0pg")])
        before_ends, _ = _open_ends(props)
        out, stats = consolidate_props(props, smooth_grade=True)
        self.assertEqual(stats.straight_after, 1)
        self.assertIn("156pg", out[0]["mdl"])
        after_ends, library = _open_ends(out)
        self.assertEqual(before_ends, after_ends)
        self.assertEqual(joincheck.audit_props(out, library, allowed_open=before_ends), [])

    def test_downhill_reversed_chain(self):
        props = _make_downhill([256, 256])
        before_ends, library = _open_ends(props)
        self.assertEqual(joincheck.audit_props(props, library, allowed_open=before_ends), [])
        out, stats = consolidate_props(props, smooth_grade=False)
        self.assertEqual(stats.straight_after, 1)
        after_ends, library2 = _open_ends(out)
        self.assertEqual(before_ends, after_ends)
        self.assertEqual(joincheck.audit_props(out, library2, allowed_open=before_ends), [])

    def test_diagonal_1rt_flat_chain(self):
        props = _make_flat_chain([128, 128], yaw=-90, direction="1rt")
        before_ends, _ = _open_ends(props)
        out, stats = consolidate_props(props, smooth_grade=False)
        self.assertEqual(stats.straight_after, 1)
        after_ends, library = _open_ends(out)
        self.assertEqual(before_ends, after_ends)
        self.assertEqual(joincheck.audit_props(out, library, allowed_open=before_ends), [])

    def test_scenery_props_are_ignored(self):
        props = _make_flat_chain([32, 32])
        props.append(
            {
                "mdl": "models/props_2fort/frog.mdl",
                "pos": [999, 999, 999],
                "ang": (0, 0, 0),
            }
        )
        out, stats = consolidate_props(props, smooth_grade=False)
        self.assertEqual(stats.straight_after, 1)
        self.assertTrue(any("frog.mdl" in prop["mdl"] for prop in out))

    def test_arc_breaks_the_run(self):
        catalog = get_catalog()
        flat_a = catalog.get("0fw", "0pg", 64)
        flat_b = catalog.get("0fw", "0pg", 64)
        # Synthetic "arc" that is not a straight — use a real arc from the library.
        arc_model = (
            "models/trakpak3_rsg/arcs/r8192/"
            "a0fw_4lt_left_311pg_+5920x-2400x+204up.mdl"
        )
        install_manifest_library()
        arc = track.track_model_library[arc_model]
        yaw = -90
        props = [
            {"mdl": flat_a.model, "pos": [0, 0, 0], "ang": (0, yaw, 0)},
        ]
        after_flat = tools.rot_orth(flat_a.move, yaw)
        arc_pos = [float(after_flat[i]) for i in range(3)]
        props.append({"mdl": arc_model, "pos": arc_pos, "ang": (0, yaw, 0)})
        after_arc = [
            arc_pos[i] + float(tools.rot_orth(arc["Move"], yaw)[i]) for i in range(3)
        ]
        props.append({"mdl": flat_b.model, "pos": after_arc, "ang": (0, yaw, 0)})

        out, stats = consolidate_props(props, smooth_grade=False)
        self.assertEqual(stats.runs_merged, 0)
        self.assertEqual(len([p for p in out if "/straights/" in p["mdl"]]), 2)


class ConsolidateVmfTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        install_manifest_library()

    def test_vmf_text_round_trip_preserves_ends(self):
        props = _make_flat_chain([48, 48, 32])
        before_ends, _ = _open_ends(props)
        text = _vmf_from_props(props)
        new_text, stats = consolidate_vmf_text(text, smooth_grade=False)
        self.assertEqual(stats.straight_after, 1)
        after_props = joincheck.parse_vmf_track_props(new_text)
        after_ends, library = _open_ends(after_props)
        self.assertEqual(before_ends, after_ends)
        self.assertEqual(
            joincheck.audit_props(after_props, library, allowed_open=before_ends),
            [],
        )


if __name__ == "__main__":
    unittest.main()
