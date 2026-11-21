"""Synthetic sectors for the slope-limited height field.

No map is built. Track samples are planted on sectors, the same calls the
main flow makes are run, and the grid is checked directly.
"""

import math
import os
import random
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, heightmap, noisefield, sectors, terrain, tools

SIZE = 2400
SPAN = 13  # 12 gaps, so nodes sit on a 200-unit lattice


class HeightFieldTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))
        # display_perlin_layers is the only matplotlib caller, and it
        # imports pyplot itself. Importing the module must not pull it in.
        assert "matplotlib.pyplot" not in sys.modules

    def setUp(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        self.terrain = terrain.get()
        self._saved_terrain = dict(self.terrain)
        self._saved_cfg = {
            "sector_real_size": cfg.CFG["sector_real_size"],
            "noise_grid_per_sector": cfg.CFG["noise_grid_per_sector"],
            "noise_floor_ceiling_spillover_slope": cfg.CFG[
                "noise_floor_ceiling_spillover_slope"
            ],
            "sector_minimum_height": cfg.CFG["sector_minimum_height"],
        }
        cfg.CFG["sector_real_size"] = SIZE
        cfg.CFG["noise_grid_per_sector"] = SPAN
        cfg.CFG["noise_floor_ceiling_spillover_slope"] = 2
        cfg.CFG["sector_minimum_height"] = 16
        # Constant horizon fraction so the mountain mask cannot add slope.
        self.terrain.update(
            {
                "seed": 1,
                "height_terrain_minimum_to_floor": 0,
                "height_terrain_minimum_to_ceiling": 0,
                "height_terrain_flat_in_radius_around_track": 150,
                "height_track_to_terrain": -35,
                "cut_power": 4,
                "cut_scale": 150,
                "cut_basewidth": 150,
                "cut_slump": 0.9,
                "ramp_near_slope": 2,
                "ramp_flank_slope": 1,
                "ramp_near_run": 512,
                "flat_horizon_fraction": 0.95,
                "mountain_horizon_fraction": 0.95,
                "mountain_coverage": 0.45,
                "mountain_gain": 1.35,
                "terrace_distance": 0,
                "detail_amplitude": 0,
                "height_blur_passes": 3,
                "track_blend_ratio": 4,
                "track_field_scan_cap": 96,
                "track_smooth_length": 240,
                "track_z_power": 2,
                "track_cluster_distance": 200,
                "track_cluster_height": 64,
                "track_carve_count": 3,
            }
        )

    def tearDown(self):

        self.terrain.clear()
        self.terrain.update(self._saved_terrain)
        cfg.CFG.update(self._saved_cfg)
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()

    def _plant(self, x, y, floor, ceiling, points):

        before = set(sectors.Sectors)
        sectors.new_sector(x, y, floor, ceiling)
        created = set(sectors.Sectors) - before
        self.assertEqual(len(created), 1, "sector was not created")
        data = sectors.Sectors[created.pop()]
        data["neighbors"] = [False, False, False, False]
        if points:
            data["points"] = list(points)
            sectors.build_kdtree_for_sector(data)
        else:
            data["points"] = []
            data["kdtree"] = None
        return data

    def _line(self, x, z, y0, y1, step=40):

        count = int(round((y1 - y0) / step))
        return [(float(x), y0 + i * step, float(z)) for i in range(count + 1)]

    def _finish(self, relax=True):

        heightmap.generate_sector_heightmaps()
        sectors.merge_edges()
        sectors.blur_min_max_grids()
        heightmap.cut_and_fill_sector_heightmaps()
        if relax:
            heightmap.relax_heightmaps()

    def _heights_along_y(self, sector, noise_y):

        grid = sector["grid"]["height"]
        return [grid[x][noise_y][0] for x in range(len(grid))]

    def test_ramp_slope_starts_at_the_cut_and_eases_toward_the_flank(self):

        # Fine differences on the curve itself, before the grid and the carve.
        near, flank, shoulder = 2.0, 1.0, 512.0
        tall = 8000.0
        short = 900.0

        def slope_at(run, target):
            step = 1.0
            rise0 = heightmap.ramp_rise(run, target, near, flank, shoulder)
            rise1 = heightmap.ramp_rise(run + step, target, near, flank, shoulder)
            return (rise1 - rise0) / step

        self.assertEqual(heightmap.ramp_rise(0, tall, near, flank, shoulder), 0.0)
        # Opening slope is the 2:1 cut, not a flat line and not a cliff.
        self.assertGreater(slope_at(0.0, tall), 1.9)
        self.assertLess(slope_at(0.0, tall), 2.05)

        runs = [i * 25.0 for i in range(0, 160)]
        for target in (tall, short):
            previous = -1.0
            for run in runs:
                rise = heightmap.ramp_rise(run, target, near, flank, shoulder)
                self.assertGreaterEqual(rise, previous)
                self.assertLessEqual(rise, target + 1e-6)
                self.assertLessEqual(slope_at(run, target), near + 0.02)
                previous = rise

        # Well past the shoulder, a tall hillside is down near the 1:1 flank
        # and still far from the ceiling. A short one has already arrived.
        self.assertLess(slope_at(2000.0, tall), flank + 0.05)
        self.assertGreater(
            heightmap.ramp_rise(2000.0, short, near, flank, shoulder), short * 0.85
        )
        self.assertLess(
            heightmap.ramp_rise(2000.0, tall, near, flank, shoulder), tall * 0.45
        )

    def test_grid_follows_the_ramp_and_does_not_cliff(self):

        points = self._line(0.0, 200.0, -400.0, SIZE + 400.0)
        sector = self._plant(0, 0, 0, 8000, points)
        # No blur yet: the stored node is the ramp plus the carve.
        self._finish(relax=False)

        bed = 200.0 - 35.0
        mid = SPAN // 2
        heights = self._heights_along_y(sector, mid)
        spacing = SIZE / (SPAN - 1)

        for x in range(SPAN):
            real_x = x * spacing
            real_y = mid * spacing
            info = heightmap.track_field(sector, real_x, real_y, self.terrain)
            run = max(0.0, info["distance"] - 150.0)
            lo, hi = heightmap._node_limits(sector, x, mid, self.terrain)
            target = (hi - bed) * 0.95
            expected = bed + heightmap.ramp_rise(run, target, 2.0, 1.0, 512.0)
            expected = heightmap.carve_to_tracks(expected, info["tracks"], self.terrain)
            expected = min(max(expected, lo), hi)
            self.assertAlmostEqual(heights[x], expected, delta=1.0)

        # Far side of a tall sector is still a hillside, not the ceiling.
        self.assertLess(heights[-1], 4000.0)
        self.assertGreater(heights[-1], bed + 800.0)

        for x in range(SPAN - 1):
            chord = (heights[x + 1] - heights[x]) / spacing
            self.assertLessEqual(chord, 2.05)
            self.assertGreaterEqual(chord, -0.05)

        # Past ~2 shoulder-lengths the chords have eased to the 1:1 flank.
        # Closer than that the curve is still coming down off the 2:1 cut.
        for x in range(8, SPAN - 1):
            chord = (heights[x + 1] - heights[x]) / spacing
            self.assertLessEqual(chord, 1.1)
        # And the distance used for a straight rail is the perpendicular
        # distance, not a smooth-min collapsed toward zero.
        info = heightmap.track_field(sector, 1000.0, mid * spacing, self.terrain)
        self.assertAlmostEqual(info["distance"], 1000.0, delta=5.0)

    def test_short_sector_still_lifts_the_horizon(self):

        near, flank, shoulder = 2.0, 1.0, 512.0
        run = 2000.0
        short_target = 900.0
        tall_target = 7000.0
        short_rise = heightmap.ramp_rise(run, short_target, near, flank, shoulder)
        tall_rise = heightmap.ramp_rise(run, tall_target, near, flank, shoulder)
        self.assertGreater(short_rise / short_target, 0.85)
        self.assertLess(tall_rise / tall_target, 0.5)
        # Same opening slope in both. The short one is not squashed flat.
        step = 50.0
        short_chord = (
            heightmap.ramp_rise(step, short_target, near, flank, shoulder) / step
        )
        tall_chord = heightmap.ramp_rise(step, tall_target, near, flank, shoulder) / step
        self.assertGreater(short_chord, 1.5)
        self.assertGreater(tall_chord, 1.5)

    def test_midpoint_between_two_tracks_has_no_crease_or_height_jump(self):

        points = []
        for i in range(-20, 21):
            y = i * 40.0
            points.append((0.0, y, 0.0))
            points.append((600.0, y, 400.0))
        sector = self._plant(0, 0, 0, 4000, points)

        xs = [i * 15.0 for i in range(0, 41)]
        smooth_z = []
        smooth_d = []
        hard_z = []
        hard_d = []
        for x in xs:
            info = heightmap.track_field(sector, x, 0.0, self.terrain)
            smooth_z.append(info["z"])
            smooth_d.append(info["distance"])
            dist, idx = sector["kdtree"].query((x, 0.0))
            hard_z.append(points[int(idx)][2])
            hard_d.append(float(dist))

        self.assertLess(abs(smooth_z[0] - 0.0), 25.0)
        self.assertLess(abs(smooth_z[-1] - 400.0), 25.0)
        self.assertLess(abs(smooth_z[len(xs) // 2] - 200.0), 30.0)

        def max_second(values):
            return max(
                abs(values[i - 1] - 2.0 * values[i] + values[i + 1])
                for i in range(1, len(values) - 1)
            )

        # The hard field flips rail z by the full 400 at the midline.
        self.assertGreater(max(abs(hard_z[i + 1] - hard_z[i]) for i in range(len(xs) - 1)), 300.0)
        self.assertLess(max(abs(smooth_z[i + 1] - smooth_z[i]) for i in range(len(xs) - 1)), 40.0)
        self.assertLess(max_second(smooth_d), max_second(hard_d) * 0.5)

    def test_two_tracks_keep_clearance_through_blur(self):

        # Try hard to bury the rails: large grit, then the blur that used to
        # lift the averaged ground back over the cut.
        self.terrain["detail_amplitude"] = 250
        self.terrain["terrace_distance"] = 180
        self.terrain["flat_horizon_fraction"] = 0.35
        self.terrain["mountain_horizon_fraction"] = 0.95
        points = self._line(400.0, 200.0, -400.0, SIZE + 400.0)
        points += self._line(1400.0, 900.0, -400.0, SIZE + 400.0)
        sector = self._plant(0, 0, 0, 8000, points)
        self._finish(relax=True)

        grid = sector["grid"]["height"]
        low = grid[2][SPAN // 2][0]
        high = grid[7][SPAN // 2][0]
        self.assertAlmostEqual(low, 165.0, delta=1.0)
        self.assertAlmostEqual(high, 865.0, delta=1.0)
        # The low rail is not filled up to the high rail's roadbed.
        self.assertLess(low, 400.0)

        lo, hi = 0.0, 8000.0
        for x in range(SPAN):
            for y in range(SPAN):
                self.assertGreaterEqual(grid[x][y][0], lo - 1e-6)
                self.assertLessEqual(grid[x][y][0], hi + 1e-6)

        # Every distinct nearby rail, not only the nearest, still clears.
        for x in range(SPAN):
            for y in range(SPAN):
                info = heightmap.track_field(
                    sector, x * (SIZE / (SPAN - 1)), y * (SIZE / (SPAN - 1)), self.terrain
                )
                for dist, _tx, _ty, z in info["tracks"]:
                    cap = heightmap.carve_deviation(dist, self.terrain, 2.0)
                    self.assertLessEqual(grid[x][y][0], z - 35.0 + cap + 1.0)

    def test_floor_and_ceiling_hold_with_noise_and_blur(self):

        self.terrain["detail_amplitude"] = 400
        self.terrain["terrace_distance"] = 300
        self.terrain["height_terrain_minimum_to_floor"] = 20
        self.terrain["height_terrain_minimum_to_ceiling"] = 80
        points = self._line(200.0, 300.0, -400.0, SIZE + 400.0)
        sector = self._plant(0, 0, 0, 5000, points)
        self._finish(relax=True)

        lo = 0.0 + 20.0
        hi = 5000.0 - 80.0
        grid = sector["grid"]["height"]
        for x in range(SPAN):
            for y in range(SPAN):
                self.assertGreaterEqual(grid[x][y][0], lo - 1e-6)
                self.assertLessEqual(grid[x][y][0], hi + 1e-6)
                self.assertGreaterEqual(sector["grid"]["minmap"][x][y][0], lo - 1e-6)
                self.assertLessEqual(sector["grid"]["maxmap"][x][y][0], hi + 1e-6)

    def test_envelope_spreads_until_the_slope_settles(self):

        # 4000-unit floor step. At 2:1 that needs 2000 units, ten nodes of the
        # 200-unit lattice. Five fixed passes cannot reach it.
        low = self._plant(0, 0, 0, 9000, [])
        high = self._plant(1, 0, 4000, 9000, [])
        low["neighbors"] = [False, high["id"], False, False]
        high["neighbors"] = [False, False, False, low["id"]]

        heightmap.generate_sector_heightmaps()
        sectors.merge_edges()
        sectors.blur_min_max_grids()

        step = 2.0 * (SIZE / (SPAN - 1))
        edge = SPAN - 1
        # Ten nodes in from the shared edge: the high floor has arrived,
        # decayed by exactly the slope, and the original low floor is the bottom.
        arrived = low["grid"]["minmap"][edge - 8][SPAN // 2][0]
        beyond = low["grid"]["minmap"][0][SPAN // 2][0]
        high_floor = high["grid"]["minmap"][0][0][0]
        self.assertAlmostEqual(arrived, high_floor - step * 8, delta=1.0)
        self.assertAlmostEqual(beyond, 0.0, delta=1e-6)

        spacing = SIZE / (SPAN - 1)
        for grid, mode in (
            (low["grid"]["minmap"], 1),
            (high["grid"]["maxmap"], -1),
        ):
            for x in range(SPAN):
                for y in range(SPAN):
                    here = grid[x][y][0]
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if nx < 0 or ny < 0 or nx >= SPAN or ny >= SPAN:
                            continue
                        # Rise/run along an orthogonal step. Positive `mode`
                        # checks the floor (a neighbor may be higher by at most one step).
                        delta = (grid[nx][ny][0] - here) * mode
                        self.assertLessEqual(delta, step + 1e-4)

    def test_diagonal_corners_are_one_vertex(self):

        a = self._plant(0, 0, 0, 4000, [])
        e = self._plant(1, 0, 0, 4000, [])
        n = self._plant(0, 1, 0, 4000, [])
        d = self._plant(1, 1, 0, 4000, [])
        a["neighbors"] = [n["id"], e["id"], False, False]
        e["neighbors"] = [d["id"], False, False, a["id"]]
        n["neighbors"] = [False, d["id"], a["id"], False]
        d["neighbors"] = [False, False, e["id"], n["id"]]

        heightmap.generate_sector_heightmaps()
        sectors.merge_edges()

        last = SPAN - 1
        for name in ("minmap", "maxmap", "height"):
            corner = a["grid"][name][last][last]
            self.assertIs(corner, e["grid"][name][0][last])
            self.assertIs(corner, n["grid"][name][last][0])
            self.assertIs(corner, d["grid"][name][0][0])

        sectors.blur_min_max_grids()
        corner = a["grid"]["minmap"][last][last]
        self.assertIs(corner, d["grid"]["minmap"][0][0])
        corner[0] = 12345.0
        self.assertEqual(e["grid"]["minmap"][0][last][0], 12345.0)
        self.assertEqual(n["grid"]["minmap"][last][0][0], 12345.0)

    def test_mountain_field_changes_height_and_is_about_two_sectors_long(self):

        points = self._line(0.0, 100.0, -400.0, SIZE + 400.0, step=40)
        # Move the rail onto y = 0 so a whole row of nodes shares one distance.
        points = [(x, 0.0, z) for x, _y, z in self._line(0.0, 100.0, -400.0, SIZE + 400.0)]
        # The line above is along x at y=0, z=100. Rebuild properly.
        points = [(float(x), 0.0, 100.0) for x in range(-400, SIZE + 401, 40)]
        sector = self._plant(0, 0, 0, 6000, points)
        self.terrain["flat_horizon_fraction"] = 0.15
        self.terrain["mountain_horizon_fraction"] = 0.95
        self.terrain["terrace_distance"] = 0
        self.terrain["detail_amplitude"] = 0

        real_sample = noisefield.sample_named

        def patched(terrain_block, name, x, y, z=0.0):
            if name == "mountain":
                return 1.0 if x >= SIZE * 0.5 else -1.0
            return 0.0

        noisefield.sample_named = patched
        try:
            self._finish(relax=False)
        finally:
            noisefield.sample_named = real_sample

        grid = sector["grid"]["height"]
        # noise_y = 6 is 1200 units off the rail at y = 0. Same run, two masks.
        flat_height = grid[2][6][0]
        mountain_height = grid[10][6][0]
        self.assertGreater(mountain_height, flat_height + 250.0)

        # The mountain spec itself: long axis ~2 sectors, short axis a quarter
        # of that, no rotation and no warp so the axes stay put.
        spec = {
            "scale": SIZE * 2.0,
            "anisotropy": 0.25,
            "octaves": 1,
            "warp": 0,
            "rotation_sectors": 0,
            "seed_offset": 3,
        }
        long_vals = [noisefield.sample_spec(spec, 1, i * 50.0, 0.0, 0.0) for i in range(200)]
        short_vals = [noisefield.sample_spec(spec, 1, 0.0, i * 50.0, 0.0) for i in range(200)]

        def corr(values, lag_units):
            lag = int(lag_units / 50.0)
            a = values[:-lag]
            b = values[lag:]
            mean_a = sum(a) / len(a)
            mean_b = sum(b) / len(b)
            var_a = sum((v - mean_a) ** 2 for v in a)
            var_b = sum((v - mean_b) ** 2 for v in b)
            cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(len(a)))
            return cov / math.sqrt(var_a * var_b)

        # 400 units is a small step on a 2-sector (4800-unit) ridge, and a
        # large step on the 0.25-aspect short axis (1200 units).
        self.assertGreater(corr(long_vals, 400.0), 0.7)
        self.assertGreater(corr(long_vals, 400.0), corr(short_vals, 400.0) + 0.2)
        # Across about one long wavelength the field has actually changed.
        self.assertLess(corr(long_vals, SIZE * 2.0), 0.5)

    def test_terrace_warp_bends_the_slope_but_stays_mostly_monotone(self):

        points = self._line(0.0, 200.0, -400.0, SIZE + 400.0)
        sector = self._plant(0, 0, 0, 8000, points)
        self.terrain["terrace_distance"] = 220
        self.terrain["detail_amplitude"] = 0

        def patched(terrain_block, name, x, y, z=0.0):
            if name == "terrace":
                # One full swing across the sector, along the slope (x).
                return math.sin(x / SIZE * math.pi * 2.0)
            return 0.0

        real_sample = noisefield.sample_named
        noisefield.sample_named = patched
        try:
            self._finish(relax=False)
        finally:
            noisefield.sample_named = real_sample

        heights = self._heights_along_y(sector, SPAN // 2)
        # The unterraced ramp, same rail distance, so the delta is the warp.
        plain = []
        bed = 165.0
        spacing = SIZE / (SPAN - 1)
        mid = SPAN // 2
        for x in range(SPAN):
            info = heightmap.track_field(sector, x * spacing, mid * spacing, self.terrain)
            run = max(0.0, info["distance"] - 150.0)
            lo, hi = heightmap._node_limits(sector, x, mid, self.terrain)
            target = (hi - min(bed, hi)) * 0.95
            rise = heightmap.ramp_rise(run, max(target, 0.0), 2.0, 1.0, 512.0)
            height = heightmap.carve_to_tracks(bed + rise, info["tracks"], self.terrain)
            plain.append(min(max(height, lo), hi))

        self.assertGreater(max(abs(heights[i] - plain[i]) for i in range(SPAN)), 30.0)
        # Walking away from the rail, the ground does not turn into a saw.
        drops = [
            heights[x] - heights[x + 1]
            for x in range(SPAN - 1)
            if heights[x] > heights[x + 1]
        ]
        self.assertLess(max(drops, default=0.0), spacing * 0.5)
        self.assertGreater(heights[-1], heights[0] + 400.0)

    def test_query_alpha_stays_in_range(self):

        points = self._line(400.0, 200.0, -400.0, SIZE + 400.0)
        sector = self._plant(0, 0, 0, 4000, points)
        self._finish(relax=True)
        for x in (200.0, 800.0, 1600.0):
            alpha = heightmap.query_alpha((x, 1200.0, 0.0), self.terrain, sector)
            self.assertGreaterEqual(alpha, 0.0)
            self.assertLessEqual(alpha, 255.0)


def _legacy_track_samples(sector_data, x, y, radius, scan_cap):

    # The ball query this change replaced. Kept here so the new k-nearest
    # walk can be compared against it. scan_cap <= 0 still takes this path
    # in the module; the copy is what the capped path is measured against.
    tree = sector_data.get("kdtree")
    points = sector_data.get("points")
    if points is None:
        points = sector_data.get("kdtree_data")
    if tree is None or points is None or len(points) == 0:
        return []

    if len(points) == 1:
        point = points[0]
        dist = math.hypot(float(point[0]) - x, float(point[1]) - y)
        return [(dist, float(point[0]), float(point[1]), float(point[2]))]

    idxs = tree.query_ball_point((x, y), radius)
    if not idxs:
        dist, idx = tree.query((x, y))
        idxs = [int(idx)]
        dists = [float(dist)]
    else:
        dists = None

    samples = []
    for n, idx in enumerate(idxs):
        idx = int(idx)
        if idx < 0 or idx >= len(points):
            continue
        point = points[idx]
        px, py, pz = float(point[0]), float(point[1]), float(point[2])
        if dists is None:
            dist = math.hypot(px - x, py - y)
        else:
            dist = dists[n]
        if not math.isfinite(dist):
            continue
        samples.append((dist, px, py, pz))

    samples.sort(key=lambda sample: sample[0])
    cap = int(scan_cap)
    if cap > 0 and len(samples) > cap:
        samples = samples[:cap]
    return samples


def _old_clamp(sector, noise_x, noise_y, terrain_block, height):

    real_x, real_y = heightmap.convert_noise_to_real_pos(noise_x, noise_y, sector)
    info = heightmap.track_field(sector, real_x, real_y, terrain_block)
    lo, hi = heightmap._node_limits(sector, noise_x, noise_y, terrain_block)
    height = tools.clamped(height, lo, hi)
    height = heightmap.carve_to_tracks(height, info["tracks"], terrain_block)
    return tools.clamped(height, lo, hi)


def _composed_clamp(height, lo, hi, tracks, terrain_block):

    height = tools.clamped(height, lo, hi)
    height = heightmap.carve_to_tracks(height, tracks, terrain_block)
    return tools.clamped(height, lo, hi)


class ClampCacheTests(unittest.TestCase):

    # Same sector fixture as HeightFieldTests, without inheriting its tests.
    setUpClass = HeightFieldTests.__dict__["setUpClass"]
    setUp = HeightFieldTests.setUp
    tearDown = HeightFieldTests.tearDown
    _plant = HeightFieldTests._plant
    _line = HeightFieldTests._line
    _finish = HeightFieldTests._finish


    def test_clamp_window_equals_the_three_step_clamp(self):

        # The cached window is min/max only. It has to reproduce
        # clamp(lo, hi) -> carve -> clamp(lo, hi) for every height, including
        # heights the blur can invent outside the envelope, and including
        # the crossed-rail case where the carve folds onto its upper edge.
        layouts = [
            [],
            [(0.0, 0.0, 0.0, 100.0)],
            [
                (0.0, 0.0, 0.0, 100.0),
                (40.0, 40.0, 0.0, 120.0),
                (180.0, 180.0, 0.0, 400.0),
            ],
            [(0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 800.0)],
            [(12.0, 0.0, 0.0, 200.0), (12.0, 0.0, 0.0, 900.0)],
            [(5000.0, 0.0, 0.0, 200.0)],
        ]
        boxes = [(0.0, 8000.0), (100.0, 100.0), (500.0, 600.0), (-50.0, 50.0), (200.0, -10.0)]
        probes = [-1e9, -1000.0, -35.0, 0.0, 1.0, 50.0, 165.0, 400.0, 1000.0, 8000.0, 1e9]

        for tracks in layouts:
            for lo, hi in boxes:
                wlo, whi = heightmap._clamp_window(lo, hi, tracks, self.terrain)
                self.assertLessEqual(wlo, whi)
                for height in probes:
                    old = _composed_clamp(height, lo, hi, tracks, self.terrain)
                    new = min(max(height, wlo), whi)
                    self.assertEqual(new, old)

        rng = random.Random(0)
        for _ in range(200):
            lo = rng.uniform(-500.0, 2500.0)
            hi = rng.uniform(-500.0, 8000.0)
            tracks = []
            for _track in range(rng.randint(0, 5)):
                tracks.append(
                    (
                        rng.uniform(0.0, 3000.0),
                        rng.uniform(-100.0, 100.0),
                        rng.uniform(-100.0, 100.0),
                        rng.uniform(-200.0, 3000.0),
                    )
                )
            wlo, whi = heightmap._clamp_window(lo, hi, tracks, self.terrain)
            self.assertLessEqual(wlo, whi)
            for _probe in range(12):
                height = rng.uniform(-5000.0, 12000.0)
                old = _composed_clamp(height, lo, hi, tracks, self.terrain)
                self.assertEqual(min(max(height, wlo), whi), old)

    def _heights(self):

        return (-1e6, -500.0, 0.0, 80.0, 165.0, 400.0, 2000.0, 9000.0, 1e6)

    def _assert_sector_cache(self, sector):

        self.assertIn("clamp_lo", sector["grid"])
        self.assertIn("clamp_hi", sector["grid"])
        span = len(sector["grid"]["height"])
        for noise_x in range(span):
            for noise_y in range(span):
                lo, hi = heightmap._node_limits(sector, noise_x, noise_y, self.terrain)
                real_x, real_y = heightmap.convert_noise_to_real_pos(
                    noise_x, noise_y, sector
                )
                info = heightmap.track_field(sector, real_x, real_y, self.terrain)
                expect = heightmap._clamp_window(lo, hi, info["tracks"], self.terrain)
                stored = (
                    sector["grid"]["clamp_lo"][noise_x][noise_y][0],
                    sector["grid"]["clamp_hi"][noise_x][noise_y][0],
                )
                self.assertEqual(stored, expect)
                self.assertIsNot(
                    sector["grid"]["clamp_lo"][noise_x][noise_y],
                    sector["grid"]["height"][noise_x][noise_y],
                )
                for height in self._heights():
                    got = heightmap.clamp_existing_height(
                        sector, noise_x, noise_y, self.terrain, height
                    )
                    old = _old_clamp(sector, noise_x, noise_y, self.terrain, height)
                    self.assertEqual(got, old)
                    self.assertEqual(got, min(max(height, stored[0]), stored[1]))

    def test_cached_windows_match_on_parallel_stacked_and_dense_rails(self):

        parallel = self._line(200.0, 100.0, -400.0, SIZE + 400.0)
        parallel += self._line(900.0, 700.0, -400.0, SIZE + 400.0)
        wide = self._plant(0, 0, 0, 8000, parallel)

        stacked = []
        for i in range(-20, 81):
            y = i * 30.0
            stacked.append((400.0, y, 150.0))
            stacked.append((400.0, y, 900.0))
        pile = self._plant(1, 0, 0, 6000, stacked)

        # A yard dense enough that a node a sector away still has far more
        # than 96 samples inside the search radius.
        dense = [(i * 8.0, (i % 5) * 6.0, 200.0 + (i % 4) * 30.0) for i in range(400)]
        yard = self._plant(0, 1, 0, 5000, dense)

        self._finish(relax=False)
        for sector in (wide, pile, yard):
            self._assert_sector_cache(sector)

        # A cleared cell, and a sector with the grids removed, both fall
        # back to the recompute. The other nodes keep their windows.
        yard["grid"]["clamp_lo"][0][0][0] = None
        self.assertEqual(
            heightmap.clamp_existing_height(yard, 0, 0, self.terrain, 1234.0),
            _old_clamp(yard, 0, 0, self.terrain, 1234.0),
        )
        self.assertEqual(
            heightmap.clamp_existing_height(yard, 1, 1, self.terrain, 1234.0),
            min(
                max(1234.0, yard["grid"]["clamp_lo"][1][1][0]),
                yard["grid"]["clamp_hi"][1][1][0],
            ),
        )
        del wide["grid"]["clamp_lo"]
        del wide["grid"]["clamp_hi"]
        self.assertEqual(
            heightmap.clamp_existing_height(wide, 3, 4, self.terrain, -200.0),
            _old_clamp(wide, 3, 4, self.terrain, -200.0),
        )

    def _snap_heights(self):

        snap = []
        for sector in sectors.get_all().values():
            grid = sector["grid"]["height"]
            span = len(grid)
            snap.append(
                [[grid[x][y][0] for y in range(span)] for x in range(span)]
            )
        return snap

    def _restore_heights(self, snap):

        for sector, rows in zip(sectors.get_all().values(), snap):
            grid = sector["grid"]["height"]
            span = len(grid)
            for x in range(span):
                for y in range(span):
                    grid[x][y][0] = rows[x][y]

    def test_shared_edge_keeps_each_sectors_window_through_relax(self):

        low = self._plant(0, 0, 0, 4000, self._line(200.0, 80.0, -400.0, SIZE + 400.0))
        high = self._plant(
            1, 0, 2000, 8000, self._line(SIZE + 300.0, 1400.0, -400.0, SIZE * 2)
        )
        low["neighbors"] = [False, high["id"], False, False]
        high["neighbors"] = [False, False, False, low["id"]]
        self._finish(relax=False)

        last = SPAN - 1
        mid = SPAN // 2
        self.assertIs(low["grid"]["height"][last][mid], high["grid"]["height"][0][mid])
        self.assertIsNot(
            low["grid"]["clamp_lo"][last][mid], high["grid"]["clamp_lo"][0][mid]
        )
        self.assertIsNot(
            low["grid"]["clamp_hi"][last][mid], high["grid"]["clamp_hi"][0][mid]
        )
        # Different floor and different rails, so the windows are not copies.
        self.assertNotEqual(
            (
                low["grid"]["clamp_lo"][last][mid][0],
                low["grid"]["clamp_hi"][last][mid][0],
            ),
            (
                high["grid"]["clamp_lo"][0][mid][0],
                high["grid"]["clamp_hi"][0][mid][0],
            ),
        )

        before = self._snap_heights()
        heightmap.relax_heightmaps()
        cached = self._snap_heights()

        self._restore_heights(before)
        original = heightmap.clamp_existing_height

        def recompute(sector_data, noise_x, noise_y, terrain_block, height):
            return _old_clamp(sector_data, noise_x, noise_y, terrain_block, height)

        heightmap.clamp_existing_height = recompute
        try:
            heightmap.relax_heightmaps()
            recomputed = self._snap_heights()
        finally:
            heightmap.clamp_existing_height = original

        self.assertEqual(cached, recomputed)

    def _assert_same_samples(self, old, new):

        # Same points, and distances within a ulp of the old hypot. An exact
        # tie at the cap may swap which of the tied points fills the last
        # slot; nothing farther out, and nothing strictly closer, may move.
        self.assertEqual(len(old), len(new))
        old_pts = {(sample[1], sample[2], sample[3]): sample[0] for sample in old}
        new_pts = {(sample[1], sample[2], sample[3]): sample[0] for sample in new}
        if set(old_pts) == set(new_pts):
            for key, dist in new_pts.items():
                self.assertAlmostEqual(dist, old_pts[key], delta=1e-6)
            return
        cutoff = max(max(old_pts.values()), max(new_pts.values()))
        for key in set(old_pts) ^ set(new_pts):
            dist = old_pts[key] if key in old_pts else new_pts[key]
            self.assertAlmostEqual(dist, cutoff, delta=1e-9)

    def test_track_samples_match_the_capped_ball(self):

        rails = []
        for i in range(-30, 90):
            y = i * 25.0
            rails.append((0.0, y, 50.0))
            rails.append((480.0, y + 3.0, 600.0))
        sector = self._plant(0, 0, 0, 4000, rails)
        for query in ((40.0, 100.0), (240.0, 800.0), (2000.0, -500.0)):
            nearest, _idx = sector["kdtree"].query(query)
            radius = max(float(nearest) * 4.0, float(nearest) + 240.0, 240.0)
            old = _legacy_track_samples(sector, query[0], query[1], radius, 96)
            new = heightmap._track_samples(sector, query[0], query[1], radius, 96)
            self._assert_same_samples(old, new)

        # Stacked rails: each xy is two samples with one distance. The cap
        # lands between pairs, so the set is the same; only pair order can move.
        stacked = []
        for i in range(-40, 41):
            y = i * 15.0
            stacked.append((0.0, y, 0.0))
            stacked.append((0.0, y, 500.0))
        pile = self._plant(1, 0, 0, 4000, stacked)
        old = _legacy_track_samples(pile, 60.0, 7.0, 500.0, 96)
        new = heightmap._track_samples(pile, 60.0, 7.0, 500.0, 96)
        self.assertGreater(len(pile["kdtree"].query_ball_point((60.0, 7.0), 500.0)), 96)
        self.assertEqual(len(old), 96)
        self._assert_same_samples(old, new)

        # Far from a dense yard: the ball holds well over 96 points, and the
        # 96 nearest are a unique set (no shared distance at the cutoff).
        dense = [(i * 5.0, (i % 7) * 1.5, 100.0 + i) for i in range(-250, 251)]
        yard = self._plant(0, 1, 0, 4000, dense)
        query = (0.0, 1500.0)
        radius = 8000.0
        ball = yard["kdtree"].query_ball_point(query, radius)
        self.assertGreater(len(ball), 96)
        old = _legacy_track_samples(yard, query[0], query[1], radius, 96)
        new = heightmap._track_samples(yard, query[0], query[1], radius, 96)
        self.assertEqual(len(new), 96)
        self._assert_same_samples(old, new)
        self.assertNotAlmostEqual(old[95][0], old[94][0], delta=1e-9)

        # A sample exactly on the radius stays in. The next one does not.
        edge = self._plant(
            2,
            0,
            0,
            4000,
            [(0.0, 0.0, 5.0), (100.0, 0.0, 15.0), (300.0, 0.0, 25.0)],
        )
        old = _legacy_track_samples(edge, 0.0, 0.0, 100.0, 96)
        new = heightmap._track_samples(edge, 0.0, 0.0, 100.0, 96)
        self.assertEqual(sorted((sample[1], sample[2]) for sample in old), [(0.0, 0.0), (100.0, 0.0)])
        self._assert_same_samples(old, new)

        # Nothing in range: the single nearest, even though it is outside.
        old = _legacy_track_samples(edge, 50.0, 50.0, 1.0, 96)
        new = heightmap._track_samples(edge, 50.0, 50.0, 1.0, 96)
        self.assertEqual(len(new), 1)
        self.assertGreater(new[0][0], 1.0)
        self._assert_same_samples(old, new)

        lone = self._plant(2, 1, 0, 4000, [(12.0, -4.0, 9.0)])
        self.assertEqual(
            heightmap._track_samples(lone, 0.0, 0.0, 0.0, 96),
            _legacy_track_samples(lone, 0.0, 0.0, 0.0, 96),
        )
        self.assertEqual(
            heightmap._track_samples(lone, 0.0, 0.0, 0.0, 0),
            _legacy_track_samples(lone, 0.0, 0.0, 0.0, 0),
        )
        empty = self._plant(3, 0, 0, 4000, [])
        self.assertEqual(heightmap._track_samples(empty, 0.0, 0.0, 100.0, 96), [])

        # No cap returns the whole ball, distances included, in ball order.
        old = _legacy_track_samples(yard, 10.0, 20.0, 400.0, 0)
        new = heightmap._track_samples(yard, 10.0, 20.0, 400.0, 0)
        self.assertGreater(len(new), 96)
        self.assertEqual(old, new)
        self.assertEqual(
            heightmap._track_samples(yard, 10.0, 20.0, 400.0, -3),
            _legacy_track_samples(yard, 10.0, 20.0, 400.0, -3),
        )

    def test_height_grid_matches_the_ball_sampler(self):

        points = self._line(0.0, 200.0, -400.0, SIZE + 400.0)
        points += self._line(700.0, 1100.0, -400.0, SIZE + 400.0)

        def run(sampler):
            sectors.Sectors.clear()
            sectors.sector_lookup_grid.clear()
            sector = self._plant(0, 0, 0, 8000, points)
            original = heightmap._track_samples
            heightmap._track_samples = sampler
            try:
                self._finish(relax=True)
                grid = sector["grid"]["height"]
                return [
                    [grid[x][y][0] for y in range(SPAN)] for x in range(SPAN)
                ]
            finally:
                heightmap._track_samples = original

        old = run(_legacy_track_samples)
        new = run(heightmap._track_samples)
        for x in range(SPAN):
            for y in range(SPAN):
                self.assertEqual(old[x][y], new[x][y])
