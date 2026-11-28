"""Distance from the track centerline to the nearest sector wall.

Fits and links sectors for one VMF, then prints clearance, a histogram,
the closest points, unlinked cardinal crossings, and corkscrew breaks.
The sample is the centerline. The rails sit about half a gauge closer.
Handmade points whose nearest wall is the sector-grid edge are left out
of the totals, and the count is printed. Samples in no sector are counted
on their own, not as a clearance of 0. This checker does not lay
trackhammer track, so every curve it samples is handmade.

Usage:
    python3 check_wall_clearance.py path/to/map.vmf
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from railmancer import cfg, lines, parser, sectors


def main(argv):

    if len(argv) != 2:
        print("usage: python3 check_wall_clearance.py path/to/map.vmf")
        return 2

    cfg.initialize(os.path.join(ROOT, "railmancer", "config.json"))
    lines.Beziers.clear()
    lines.sampled_points.clear()
    lines.staged_points.clear()
    sectors.Sectors.clear()
    sectors.sector_lookup_grid.clear()

    parser.import_track(argv[1])
    lines.encode_lines()
    sectors.build_fit()
    sectors.link()
    sectors.report_wall_clearance()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
