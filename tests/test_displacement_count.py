"""Displacement brushes per sector side.

Power stays 3. The count follows displacement_target_size, and every
edge stays on the 16-unit grid.
"""

import unittest

from railmancer.compile import displacement_subdivisions


class DisplacementCountTests(unittest.TestCase):

    def test_shipped_sector_is_three_by_three(self):

        # 3264 / 1088 = 3 exactly, and 3264 / 16 = 204 is divisible by 3.
        self.assertEqual(displacement_subdivisions(3264, 1088), 3)

    def test_non_divisor_snaps_onto_the_16_grid(self):

        # 3200 / 16 = 200 cells. round(3200 / 1088) = 3, and 200 % 3 != 0.
        # Among divisors, 4 pieces of 800 are closer to 1088 than 2 of 1600.
        count = displacement_subdivisions(3200, 1088)
        self.assertEqual(count, 4)
        self.assertEqual((3200 // 16) % count, 0)
        self.assertEqual(3200 / count, 800)
        self.assertEqual(800 % 16, 0)

    def test_one_piece_when_the_target_is_the_whole_sector(self):

        self.assertEqual(displacement_subdivisions(3264, 3264), 1)
        self.assertEqual(displacement_subdivisions(3264, 100000), 1)
