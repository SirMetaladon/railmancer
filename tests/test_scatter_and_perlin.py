"""Scatter placement and the in-tree Perlin field.

Scatter is a seeded density of (x, y, z). Full sky walls get more trees and
keep each model's box off the wall. Partial walls are not part of that.
Perlin replaces the `noise` package: same call, deterministic from `base`.
"""

import math
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import cfg, compile, heightmap, perlin, sectors, terrain, vmfpy

SIZE = 2400


class PerlinTests(unittest.TestCase):

    def test_same_base_is_the_same_field_and_a_scalar_matches_the_array(self):

        a = perlin.pnoise3(0.2, -0.4, 0.7, octaves=2, base=3)
        b = perlin.pnoise3(0.2, -0.4, 0.7, octaves=2, base=3)
        other = perlin.pnoise3(0.2, -0.4, 0.7, octaves=2, base=4)
        self.assertEqual(a, b)
        self.assertNotEqual(a, other)

        xs = [0.0, 0.2, 1.3]
        ys = [-0.4, 0.5, 2.0]
        zs = [0.7, 0.1, -1.0]
        grid = perlin.pnoise3(xs, ys, zs, octaves=3, persistence=0.5, lacunarity=2.0, base=9)
        for index in range(3):
            self.assertEqual(
                float(grid[index]),
                perlin.pnoise3(xs[index], ys[index], zs[index], octaves=3, base=9),
            )

    def test_range_is_near_zero_and_a_step_is_continuous(self):

        values = [
            perlin.pnoise3(x * 0.17, y * 0.13, 0.2, octaves=1, base=1)
            for x in range(-8, 9)
            for y in range(-8, 9)
        ]
        self.assertGreater(max(values), 0.2)
        self.assertLess(min(values), -0.2)
        self.assertLess(abs(sum(values) / len(values)), 0.25)
        for value in values:
            self.assertLess(abs(value), 1.25)

        left = perlin.pnoise3(1.0, 1.0, 1.0, base=2)
        right = perlin.pnoise3(1.001, 1.0, 1.0, base=2)
        self.assertLess(abs(left - right), 0.02)

    def test_an_extra_octave_moves_the_value_and_stays_bounded(self):

        one = perlin.pnoise3(0.4, 0.6, 0.1, octaves=1, base=5)
        two = perlin.pnoise3(0.4, 0.6, 0.1, octaves=2, persistence=0.5, base=5)
        self.assertNotEqual(one, two)
        samples = [
            perlin.pnoise3(i * 0.3, 0.2, -0.4, octaves=4, persistence=0.5, base=5)
            for i in range(20)
        ]
        self.assertTrue(all(abs(sample) < 2.0 for sample in samples))


class ScatterTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))

    def setUp(self):

        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        vmfpy.Entities.clear()
        self.terrain = terrain.get()
        self._saved = dict(self.terrain)
        self._saved_models = {
            path: dict(model) for path, model in terrain.biome()["models"].items()
        }
        self._saved_size = cfg.CFG["sector_real_size"]
        self._saved_span = cfg.CFG["noise_grid_per_sector"]
        cfg.CFG["sector_real_size"] = SIZE
        cfg.CFG["noise_grid_per_sector"] = 5
        self.terrain.update(
            {
                "seed": 7,
                "maximum_models_per_1kx1k": 40,
                "density_edge_multiplier": 6,
                "density_edge_width": 600,
                "density_edge_cutoff": 0,
                "wall_clearance": 64,
                "tree_hard_distance": 128,
                "tree_fade_distance": 128,
                "detail_amplitude": 0,
                "terrace_distance": 0,
                "height_terrain_minimum_to_floor": 0,
                "height_terrain_minimum_to_ceiling": 0,
            }
        )

    def tearDown(self):

        self.terrain.clear()
        self.terrain.update(self._saved)
        models = terrain.biome()["models"]
        models.clear()
        models.update(self._saved_models)
        cfg.CFG["sector_real_size"] = self._saved_size
        cfg.CFG["noise_grid_per_sector"] = self._saved_span
        sectors.Sectors.clear()
        sectors.sector_lookup_grid.clear()
        vmfpy.Entities.clear()

    def _sector(self, x, y, floor=0, ceiling=4000):

        before = set(sectors.Sectors)
        sectors.new_sector(x, y, floor, ceiling)
        data = sectors.Sectors[(set(sectors.Sectors) - before).pop()]
        data["neighbors"] = [False, False, False, False]
        data["points"] = []
        data["kdtree"] = None
        return data

    def _one_model(self, exclusion, clearance, weight=1):

        models = terrain.biome()["models"]
        models.clear()
        models["models/test/tree.mdl"] = {
            "weight": weight,
            "exclusion_radius": exclusion,
            "base_radius": 20,
            "wall_clearance": clearance,
            "steepness": 999,
            "grouping": "tree",
        }

    def _flat_heights(self):

        heightmap.generate_sector_heightmaps()

    def _props(self):

        return [entity for entity in vmfpy.Entities if isinstance(entity, dict)]

    def test_full_wall_keeps_the_box_inside_and_props_keep_their_spacing(self):

        # East side is a real neighbor, so that edge is not a sky wall.
        # The other three are. Clearance is the prop's own wall_clearance
        # plus the 16-unit sky brush.
        west = self._sector(0, 0)
        east = self._sector(1, 0)
        west["neighbors"][1] = east["id"]
        east["neighbors"][3] = west["id"]
        self._one_model(exclusion=80, clearance=50)
        self._flat_heights()
        compile.scatter_placables()
        props = [prop for prop in self._props() if prop["sector_id"] == west["id"]]
        self.assertGreater(len(props), 5)
        need = 50 + 16
        positions = []
        for prop in props:
            x, y, _z = prop["pos"]
            positions.append((x, y))
            self.assertGreaterEqual(x - 0, need)
            self.assertGreaterEqual(y - 0, need)
            self.assertGreaterEqual(SIZE - y, need)
            # The shared east edge is not a full wall, so it is not inset.
            self.assertLess(x, SIZE)
        for i, a in enumerate(positions):
            for b in positions[i + 1 :]:
                self.assertGreaterEqual(math.hypot(a[0] - b[0], a[1] - b[1]), 80)
        self.assertEqual(len(positions), len(set(positions)))

        vmfpy.Entities.clear()
        compile.scatter_placables()
        again = [
            prop["pos"]
            for prop in self._props()
            if prop["sector_id"] == west["id"]
        ]
        self.assertEqual(again, [prop["pos"] for prop in props])

    def test_density_boosts_a_full_wall_and_ignores_a_partial_one(self):

        sector = self._sector(0, 0)
        sector["neighbors"] = ["north-id", False, False, False]
        center = compile.density_at(SIZE * 0.5, SIZE * 0.5, 0, sector)
        near_full = compile.density_at(SIZE - 200, SIZE * 0.5, 0, sector)
        in_cutoff = compile.density_at(SIZE - 10, SIZE * 0.5, 0, sector)
        near_partial = compile.density_at(SIZE * 0.5, SIZE - 200, 0, sector)
        self.terrain["density_edge_cutoff"] = 80
        in_cutoff = compile.density_at(SIZE - 10, SIZE * 0.5, 0, sector)
        self.assertAlmostEqual(center, 1.0)
        self.assertGreater(near_full, center + 1.0)
        self.assertEqual(in_cutoff, 0.0)
        self.assertAlmostEqual(near_partial, 1.0)

    def test_a_fractional_sector_is_not_rounded_down_to_nothing(self):

        # 200-unit sector with no sky walls. 40 trees per 1k square is 1.6
        # expected. Over many seeds the mean stays near 1.6, not 1 or 0.
        cfg.CFG["sector_real_size"] = 200
        self.terrain["maximum_models_per_1kx1k"] = 40
        self.terrain["density_edge_multiplier"] = 0
        self.terrain["density_edge_width"] = 0
        self.terrain["density_edge_cutoff"] = 0
        self._one_model(exclusion=1, clearance=0)
        counts = []
        for seed in range(40):
            self.terrain["seed"] = seed
            sectors.Sectors.clear()
            sectors.sector_lookup_grid.clear()
            vmfpy.Entities.clear()
            sector = self._sector(0, 0)
            sector["neighbors"] = ["n", "e", "s", "w"]
            self._flat_heights()
            compile.scatter_placables()
            counts.append(len(self._props()))
        mean = sum(counts) / len(counts)
        self.assertGreater(mean, 1.1)
        self.assertLess(mean, 2.2)
        self.assertGreater(max(counts), 1)
