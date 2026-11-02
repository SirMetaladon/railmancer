"""Check a TrackPack 3 VMF the way the generator checks itself.

Every track-prop endpoint (position and rail heading) must show up twice:
one piece's end against the next piece's start. A count of 1 is a gap or an
open run end. A count of 3 or more means three rails meet, which is invalid.
Open ends are checked against move_in_trackspace, one track apart.

Usage:
    python3 check_track_vmf.py path/to/map.vmf
"""

import sys
import types

# Headless: the track library imports a drawing module that wants Tk.
sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer.joincheck import (
    audit_props,
    library_from_prop_names,
    parse_vmf_track_props,
    tally_endpoints,
)


def main(argv):
    if len(argv) != 2:
        print("usage: python3 check_track_vmf.py path/to/map.vmf")
        return 2

    with open(argv[1], "r", encoding="utf-8", errors="replace") as handle:
        props = parse_vmf_track_props(handle.read())

    if not props:
        print(f"no trakpak track props found in {argv[1]}")
        return 1

    library, unknown = library_from_prop_names(props)
    if unknown:
        print("could not read piece geometry from these model names:")
        for model in unknown:
            print(f"  {model}")
        return 1

    counts, _where = tally_endpoints(props, library)
    problems = audit_props(props, library)
    paired = sum(1 for count in counts.values() if count == 2)
    opens = [key for key, count in counts.items() if count == 1]
    junctions = sum(1 for count in counts.values() if count >= 3)

    print(
        f"{argv[1]}: {len(props)} track props, "
        f"{paired} paired joints, {len(opens)} open ends, {junctions} invalid junctions"
    )
    if opens:
        print("open ends (only the start and end of a run should appear here):")
        for key in opens:
            print(f"  {key[0]} heading {key[1]}")
    if problems:
        print("problems:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print("every joint is shared by exactly two endpoints")
    if opens:
        print("open ends are spaced by move_in_trackspace")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
