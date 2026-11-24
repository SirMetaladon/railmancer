"""2-D cross product used to spot a straight bezier.

NumPy 2 dropped np.cross on length-2 vectors. The replacement is the
scalar z-component, which is what np.cross used to return here.
"""

import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import lines


class BezierCrossTests(unittest.TestCase):

    def test_straight_pair_stays_collinear_and_a_bend_does_not(self):

        straight = lines.convert_nodes_to_bezier(
            (0.0, 0.0, 0.0),
            (1000.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        )
        bent = lines.convert_nodes_to_bezier(
            (0.0, 0.0, 0.0),
            (0.0, 1000.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        )
        self.assertEqual(len(straight), 1)
        self.assertEqual(len(bent), 1)
        # The collinear branch places the handles on the chord at 1/3 and 2/3.
        # A bend does not.
        near, far = straight[0][1], straight[0][2]
        self.assertAlmostEqual(float(near[0]), 1000.0 / 3.0)
        self.assertAlmostEqual(float(near[1]), 0.0)
        self.assertAlmostEqual(float(far[0]), 2000.0 / 3.0)
        self.assertAlmostEqual(float(far[1]), 0.0)
        bent_handle = bent[0][1]
        self.assertGreater(abs(float(bent_handle[0]) - float(near[0])), 1.0)


if __name__ == "__main__":
    unittest.main()
