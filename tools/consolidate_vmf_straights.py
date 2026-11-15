#!/usr/bin/env python3
"""CLI: consolidate fragmented TrakPak3 straights in an external VMF.

Examples:

    python3 tools/consolidate_vmf_straights.py map.vmf
    python3 tools/consolidate_vmf_straights.py map.vmf -o map_merged.vmf
    python3 tools/consolidate_vmf_straights.py map.vmf --smooth-grade
    python3 tools/consolidate_vmf_straights.py map.vmf --inplace

Then verify:

    python3 check_track_vmf.py map_consolidated.vmf
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from railmancer.consolidate_straights import main

if __name__ == "__main__":
    sys.exit(main())
