"""Consolidation of fragmented straight props.

Builds synthetic chains from the committed TrakPak3 manifest (no .mdl bytes),
merges them, and checks that the open endpoints stay exactly where they were.
Also round-trips a tiny VMF through consolidate_vmf_text.
"""

import os
import sys
import types
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, joincheck, lines, tools, track, vmfpy

# Other suites replace this with a no-op and leave it that way.
_WRITE_BEZIER = lines.write_bezier_points

from railmancer.consolidate_straights import (
    consolidate_inplace,
    consolidate_props,
    consolidate_vmf_text,
)
from railmancer.straight_catalog import ALLOWED_LENGTHS, get_catalog, parse_straight_name
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


def _straight_segments(props):
    """Each straight as (origin xyz, far xyz, piece), integers."""

    catalog = get_catalog()
    segments = []
    for prop in props:
        model = prop["mdl"].replace("\\", "/")
        if "/straights/" not in model:
            continue
        parsed = parse_straight_name(model)
        piece = catalog.get(parsed["direction"], parsed["grade_token"], parsed["length"])
        yaw = prop["ang"][1] if not isinstance(prop["ang"], (int, float)) else prop["ang"]
        rotated = tools.rot_orth(piece.move, yaw)
        origin = tuple(int(round(float(v))) for v in prop["pos"])
        far = tuple(
            int(round(float(prop["pos"][i]) + float(rotated[i]))) for i in range(3)
        )
        segments.append((origin, far, piece))
    return segments


def _directed_steps(props):
    """dz of each straight, walked from one open end to the other."""

    segments = _straight_segments(props)
    at = {}
    for index, (origin, far, _piece) in enumerate(segments):
        at.setdefault(origin, []).append((index, "origin"))
        at.setdefault(far, []).append((index, "far"))
    open_ends = [key for key, hits in at.items() if len(hits) == 1]
    if not segments or not open_ends:
        return []
    current = open_ends[0]
    seen = set()
    steps = []
    while len(seen) < len(segments):
        hits = [hit for hit in at[current] if hit[0] not in seen]
        if not hits:
            break
        index, which = hits[0]
        seen.add(index)
        origin, far, _piece = segments[index]
        nxt = far if which == "origin" else origin
        steps.append(nxt[2] - current[2])
        current = nxt
    return steps


def _peak_grade(props):
    catalog = get_catalog()
    peak = 0.0
    for prop in props:
        model = prop["mdl"].replace("\\", "/")
        if "/straights/" not in model:
            continue
        parsed = parse_straight_name(model)
        piece = catalog.get(parsed["direction"], parsed["grade_token"], parsed["length"])
        peak = max(peak, abs(piece.real_grade))
    return peak


def _assert_not_worse(test, before, after):
    before_steps = _directed_steps(before)
    after_steps = _directed_steps(after)
    before_abs = sum(abs(z) for z in before_steps)
    after_abs = sum(abs(z) for z in after_steps)
    test.assertLessEqual(after_abs, before_abs)
    test.assertLessEqual(_peak_grade(after), _peak_grade(before) + 1e-9)
    if after_steps:
        net = sum(after_steps)
        test.assertEqual(after_abs, abs(net))
        test.assertTrue(
            all(z == 0 or (z > 0) == (net > 0) for z in after_steps)
        )


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

    def test_smooth_grade_does_not_buy_pieces_with_reverse_grade(self):
        # Seven 256 @ 1.56% (length 1792, net rise +28, sum |rise| 28).
        # The old piece-count DP returned 256 @ 3.12% downhill (rise -8) plus
        # 1536 @ 2.34% uphill (rise +36): sum |rise| 44, peak 3.12, two pieces.
        props = _make_graded_chain([(256, "156pg")] * 7)
        before_ends, _ = _open_ends(props)
        out, stats = consolidate_props(props, smooth_grade=True)
        self.assertLess(stats.straight_after, stats.straight_before)
        self.assertEqual(len(out), 2)
        self.assertTrue(all("156pg" in prop["mdl"] for prop in out))
        self.assertTrue(all(prop["ang"][1] == -90 for prop in out))
        steps = _directed_steps(out)
        self.assertEqual(abs(sum(steps)), 28)
        self.assertEqual(sum(abs(z) for z in steps), 28)
        self.assertLessEqual(_peak_grade(out), 1.56)
        after_ends, library = _open_ends(out)
        self.assertEqual(before_ends, after_ends)
        self.assertEqual(joincheck.audit_props(out, library, allowed_open=before_ends), [])

    def test_smooth_grade_downhill_stays_one_sign(self):
        props = _make_downhill([256] * 7, grade="156pg")
        before_ends, _ = _open_ends(props)
        out, _stats = consolidate_props(props, smooth_grade=True)
        self.assertTrue(all("156pg" in prop["mdl"] for prop in out))
        steps = _directed_steps(out)
        self.assertEqual(abs(sum(steps)), 28)
        self.assertEqual(sum(abs(z) for z in steps), 28)
        self.assertTrue(all(z < 0 for z in steps) or all(z > 0 for z in steps))
        after_ends, library = _open_ends(out)
        self.assertEqual(before_ends, after_ends)
        self.assertEqual(joincheck.audit_props(out, library, allowed_open=before_ends), [])

    def test_flat_run_stays_flat_under_smooth_grade(self):
        # Two 8192 flats. The old DP also used two pieces, but the first
        # two-piece hit it stored was 8192 @ 3.12% up and the same downhill.
        props = _make_flat_chain([8192, 8192])
        out, stats = consolidate_props(props, smooth_grade=True)
        self.assertEqual(stats.runs_merged, 0)
        self.assertEqual(len(out), 2)
        self.assertTrue(all("0pg" in prop["mdl"] for prop in out))
        self.assertEqual(_directed_steps(out), [0, 0])

        short = _make_flat_chain([32, 32, 64])
        merged, stats = consolidate_props(short, smooth_grade=True)
        self.assertEqual(stats.straight_after, 1)
        self.assertIn("0pg", merged[0]["mdl"])
        self.assertEqual(_directed_steps(merged), [0])

    def test_smooth_grade_prefers_flat_once_peak_is_fixed(self):
        # 768 @ 3.12% (rise 24) + 256 @ 1.56% (rise 4). Peak is already 3.12
        # and nothing gentler can make rise 28 in 1024 units. The rise fits
        # on 896 units of 3.12% plus a 128 flat, which removes grade from
        # track that does not need it.
        props = _make_graded_chain([(768, "312pg"), (256, "156pg")])
        out, _stats = consolidate_props(props, smooth_grade=True)
        steps = _directed_steps(out)
        self.assertEqual(abs(sum(steps)), 28)
        self.assertEqual(sum(abs(z) for z in steps), 28)
        self.assertEqual(_peak_grade(out), 3.12)
        flat = [prop for prop in out if "0pg" in prop["mdl"]]
        self.assertEqual(len(flat), 1)
        self.assertIn("s0128_0fw_0pg_", flat[0]["mdl"])
        graded = [prop for prop in out if "0pg" not in prop["mdl"]]
        self.assertTrue(graded)
        self.assertTrue(all("312pg" in prop["mdl"] for prop in graded))
        self.assertEqual(len(out), 3)

    def test_smooth_output_is_never_worse_than_the_input(self):
        cases = [
            _make_graded_chain([(256, "156pg")] * 7),
            _make_flat_chain([8192, 8192]),
            _make_flat_chain([32, 32, 64]),
            _make_graded_chain([(256, "312pg"), (256, "0pg")]),
            _make_graded_chain([(768, "312pg"), (256, "156pg")]),
            _make_graded_chain([(256, "156pg"), (128, "0pg")]),
            _make_downhill([256] * 7, grade="156pg"),
            _make_graded_chain([(512, "234pg"), (512, "234pg")]),
            _make_graded_chain([(256, "312pg"), (256, "312pg")]),
        ]
        for props in cases:
            with self.subTest(models=[prop["mdl"].rsplit("/", 1)[-1] for prop in props]):
                out, _stats = consolidate_props(props, smooth_grade=True)
                _assert_not_worse(self, props, out)
                before_ends, _ = _open_ends(props)
                after_ends, library = _open_ends(out)
                self.assertEqual(before_ends, after_ends)
                self.assertEqual(
                    joincheck.audit_props(out, library, allowed_open=before_ends),
                    [],
                )


class ConsolidateLinesTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        install_manifest_library()
        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):
        self._entities = vmfpy.Entities
        self._beziers = lines.Beziers
        self._points = lines.sampled_points
        self._write_bezier = lines.write_bezier_points
        lines.write_bezier_points = _WRITE_BEZIER
        vmfpy.Entities = []
        lines.Beziers = []
        lines.sampled_points = []

    def tearDown(self):
        vmfpy.Entities = self._entities
        lines.Beziers = self._beziers
        lines.sampled_points = self._points
        lines.write_bezier_points = self._write_bezier

    def test_rebuilt_lines_follow_the_regraded_joints(self):
        # 256 @ 3.12% then 256 flat. The joint is 8 units up. One 512 @ 1.56%
        # covers the same ends, so that station is only 4 units up.
        props = _make_graded_chain([(256, "312pg"), (256, "0pg")])
        arc_model = (
            "models/trakpak3_rsg/arcs/r8192/"
            "a0fw_4lt_left_311pg_+5920x-2400x+204up.mdl"
        )
        arc = {
            "mdl": arc_model,
            "pos": [5000, 5000, 1000],
            "ang": (0, -90, 0),
        }
        stand = {
            "mdl": "models/trakpak3_us/switchstands/bethlehem_51a_right.mdl",
            "pos": [20, 20, 20],
            "ang": (0, 0, 0),
        }

        # What import/trackhammer would already have drawn: the pre-merge straights.
        for prop in props:
            data = track.track_model_library[prop["mdl"]]
            track.add_lines_from_track(
                np.asarray(prop["pos"], dtype=float), data, prop["ang"][1]
            )
        self.assertEqual(len(lines.Beziers), 2)
        lines.encode_lines()
        joint = _straight_segments(props)[0][1]
        old_hit = _nearest_sample(lines.sampled_points, joint)
        self.assertAlmostEqual(old_hit[2], joint[2], delta=0.2)

        vmfpy.Entities = props + [arc, stand]
        consolidate_inplace(smooth_grade=True)

        straights = [prop for prop in vmfpy.Entities if "/straights/" in prop["mdl"]]
        self.assertEqual(len(straights), 1)
        self.assertIn("156pg", straights[0]["mdl"])
        # One regraded straight plus the arc. The stand is not a rail.
        self.assertEqual(len(lines.Beziers), 2)

        lines.encode_lines()
        samples = lines.sampled_points
        new_hit = _nearest_sample(samples, joint)
        # Linear 1.56% across the whole 512: halfway is half the net rise.
        self.assertAlmostEqual(new_hit[2], joint[2] / 2.0, delta=0.75)
        self.assertGreater(abs(new_hit[2] - old_hit[2]), 2.0)

        for origin, far, _piece in _straight_segments(straights):
            self.assertLess(_distance(_nearest_sample(samples, origin), origin), 0.6)
            self.assertLess(_distance(_nearest_sample(samples, far), far), 0.6)

        arc_start = tuple(arc["pos"])
        self.assertLess(_distance(_nearest_sample(samples, arc_start), arc_start), 0.6)
        arc_far = track.process_file(arc_model)[0]["Move"]
        arc_end_z = arc["pos"][2] + arc_far[2]
        z_values = [point[2] for point in samples]
        self.assertTrue(any(abs(z - arc_end_z) < 0.6 for z in z_values))
        # The stand is not track, so it contributes no sample.
        self.assertGreater(_distance(_nearest_sample(samples, stand["pos"]), stand["pos"]), 15)


def _distance(a, b):
    return sum(abs(float(a[i]) - float(b[i])) for i in range(3))


def _nearest_sample(points, target):
    return min(points, key=lambda point: _distance(point, target))


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
