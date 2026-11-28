"""Yaw snap in rot_orth.

Hammer writes -89.9999 for a -90 degree turn. Truncating toward zero aimed
that prop at 0. A yaw within 0.001 degrees of a multiple of 90 snaps first.
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

from railmancer import tools


class RotOrthSnapTests(unittest.TestCase):

    def test_negative_eighty_nine_point_nine_is_negative_ninety(self):
        vector = (1.0, 0.0, 5.0)
        snapped = tools.rot_orth(vector, -89.9999)
        exact = tools.rot_orth(vector, -90)
        self.assertTrue(np.allclose(snapped, exact))
        # -90 degrees is one clockwise quarter: (x, y) -> (y, -x).
        self.assertTrue(np.allclose(snapped, (0.0, -1.0, 5.0)))

    def test_dust_just_past_ninety_stays_ninety(self):
        vector = (1.0, 0.0, 0.0)
        self.assertTrue(
            np.allclose(tools.rot_orth(vector, 90.0001), tools.rot_orth(vector, 90))
        )
        self.assertTrue(
            np.allclose(tools.rot_orth(vector, -90.0001), tools.rot_orth(vector, -90))
        )

    def test_angles_outside_the_dust_band_still_truncate(self):
        vector = np.array([2.0, 3.0, 4.0])
        self.assertTrue(np.allclose(tools.rot_orth(vector, 45), vector))
        self.assertTrue(np.allclose(tools.rot_orth(vector, -45), vector))
        self.assertTrue(np.allclose(tools.rot_orth(vector, 89), vector))
        self.assertTrue(np.allclose(tools.rot_orth(vector, 89.998), vector))
