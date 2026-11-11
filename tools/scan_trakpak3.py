"""List TrakPak3 track models and write data/trakpak3_models.json.

Railmancer does not read the contents of a .mdl. The filename is the
geometry: direction, grade, and the end offset are written into the name.
This script collects those names and runs each one through
railmancer.track.process_file, which is the parser the game library uses.

It does not download model bytes. A refresh asks GitHub for the file tree
(names only). A local copy, including the Steam folder Railmancer already
points at, can be scanned instead:

    C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg

From the repo root:

    python tools/scan_trakpak3.py                 # summarize the manifest
    python tools/scan_trakpak3.py --refresh       # rewrite it from GitHub
    python tools/scan_trakpak3.py --local PATH    # rewrite it from a checkout
    python tools/scan_trakpak3.py --check         # print mismatches only
"""

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from railmancer import track

MANIFEST_PATH = os.path.join(ROOT, "data", "trakpak3_models.json")
GITHUB_REPO = "MagnumMacKivler/trakpak3"
GITHUB_API = "https://api.github.com/repos/" + GITHUB_REPO

# Families that live under models/trakpak3_rsg and that Railmancer either
# parses or should be told it cannot parse. Bridge props under spl/ are
# scenery, not track, so they are left out.
TRACK_FOLDERS = ("arcs", "straights", "banked", "bends", "diamonds")
SWITCH_FOLDERS = (
    "turnouts",
    "sidings",
    "xovers",
    "wyes",
    "slips",
    "doublejunctions",
)

# Pieces named by tests/test_hand_fixed_route.py on the parallel-track
# branch. That file is not on this branch, so the list is copied here.
HAND_FIXED_ROUTE = [
    "models/trakpak3_rsg/straights/s2048_0fw_312pg_+2048x00000x+064up.mdl",
    "models/trakpak3_rsg/arcs/r8192/a0fw_4lt_left_311pg_+5920x-2400x+204up.mdl",
    "models/trakpak3_rsg/arcs/r4096/a2rt_4rt_right_-311pg_+1248x+0896x-048dn.mdl",
    "models/trakpak3_rsg/straights/s0384_2rt_279pg_+0384x+0192x+012up.mdl",
    "models/trakpak3_rsg/arcs/r8192/a1rt_2rt_right_-312pg_+1920x+0704x-064dn.mdl",
    "models/trakpak3_rsg/straights/s0128_1rt_303pg_+0128x+0032x+004up.mdl",
    "models/trakpak3_rsg/straights/s1024_1rt_303pg_+1024x+0256x+032up.mdl",
    "models/trakpak3_rsg/straights/s1536_1rt_303pg_+1536x+0384x+048up.mdl",
    "models/trakpak3_rsg/straights/s0768_1rt_303pg_+0768x+0192x+024up.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_1rt_right_-315pg_+1760x+0224x-056dn.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_8lt_left_311pg_+6144x-6144x+300up.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_2lt_left_314pg_+2944x-0704x+096up.mdl",
    "models/trakpak3_rsg/straights/s1024_2lt_279pg_+1024x-0512x+032up.mdl",
    "models/trakpak3_rsg/arcs/r4096/a0fw_2lt_left_-306pg_+2016x-0480x-064dn.mdl",
    "models/trakpak3_rsg/straights/s6144_0fw_312pg_+6144x00000x+192up.mdl",
    "models/trakpak3_rsg/straights/s3072_0fw_312pg_+3072x00000x+096up.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_8rt_right_311pg_+6144x+6144x+300up.mdl",
    "models/trakpak3_rsg/arcs/r6144/a0fw_1rt_right_315pg_+1760x+0224x+056up.mdl",
    "models/trakpak3_rsg/straights/s0512_1rt_303pg_+0512x+0128x+016up.mdl",
]

# move_in_trackspace assumes these slopes of filename-Y over filename-X.
STRAIGHT_SLOPE = {
    "0fw": 0.0,
    "1rt": 0.25,
    "1lt": -0.25,
    "2rt": 0.5,
    "2lt": -0.5,
    "4rt": 1.0,
    "4lt": -1.0,
}

# valid_next_tracks will only offer these radii. 0 is a straight.
PATHFINDER_RADII = {2048, 3072, 4096, 6144, 8192, 0}


def model_key_from_repo_path(repo_path):

    """Turn a Git tree path into the models/... key process_file expects.

    The repo stores files at Gmod/addons/trakpak3/models/trakpak3_rsg/...
    Railmancer's library key starts at models/.
    """

    marker = "/models/"
    index = repo_path.find(marker)
    if index < 0:
        return None
    return repo_path[index + 1 :]


def is_rsg_track_model(model):

    """True for track pieces in the standard-gauge pack Railmancer walks.

    trakpak3_rsg_bridge and trakpak3_rsg_guard are separate packs. The
    Steam path in railmancer.py is models/trakpak3_rsg only.
    """

    parts = model.split("/")
    if len(parts) < 4 or parts[0] != "models" or parts[1] != "trakpak3_rsg":
        return False
    if parts[2] in TRACK_FOLDERS:
        return True
    if parts[2] == "switches" and len(parts) > 3 and parts[3] in SWITCH_FOLDERS:
        return True
    return False


def family_of(model):

    parts = model.split("/")
    if parts[2] == "switches":
        return parts[3]
    return parts[2]


def parse_model(model):

    """Run process_file and keep the print it makes for an unknown family.

    Returns (routes, reason). routes is a list of dicts, or None on failure.
    """

    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink):
            routes = track.process_file(model)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    if not routes:
        note = sink.getvalue().strip() or "track.process_file returned nothing"
        return None, note
    return routes, ""


def iter_local_models(root):

    """Yield models/... keys from a checkout or a Steam trakpak folder."""

    root = os.path.abspath(root)
    bases = []
    if os.path.basename(root) == "trakpak3_rsg":
        bases.append(root)
    else:
        for dirpath, dirnames, _files in os.walk(root):
            if os.path.basename(dirpath) == "trakpak3_rsg":
                bases.append(dirpath)
                dirnames[:] = [name for name in dirnames if name != "trakpak3_rsg"]

    seen = set()
    for base in bases:
        for dirpath, _dirnames, files in os.walk(base):
            for name in files:
                if not name.endswith(".mdl"):
                    continue
                full = os.path.join(dirpath, name)
                relative = os.path.relpath(full, base).replace("\\", "/")
                model = f"models/trakpak3_rsg/{relative}"
                if model in seen or not is_rsg_track_model(model):
                    continue
                seen.add(model)
                yield model


def github_json(url):

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "railmancer-trakpak-scan",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_github_models():

    """Names only, via the Git tree API. No blobs are downloaded."""

    commit = github_json(f"{GITHUB_API}/commits/master")
    sha = commit["sha"]
    when = commit["commit"]["committer"]["date"]
    tree = github_json(f"{GITHUB_API}/git/trees/{sha}?recursive=1")
    if tree.get("truncated"):
        raise RuntimeError("GitHub truncated the tree; use --local instead")

    models = []
    for entry in tree.get("tree", []):
        path = entry.get("path", "")
        if not path.endswith(".mdl"):
            continue
        model = model_key_from_repo_path(path)
        if model and is_rsg_track_model(model):
            models.append(model)

    source = {
        "kind": "github",
        "repo": f"https://github.com/{GITHUB_REPO}",
        "commit": sha,
        "commit_date": when,
        "ref": "master",
    }
    return source, models


def local_source(root):

    sha = ""
    try:
        sha = subprocess.check_output(
            ["git", "-C", root, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sha = ""
    return {
        "kind": "local",
        "path": os.path.abspath(root),
        "commit": sha,
        "commit_date": "",
        "ref": "",
    }


def scan_models(models):

    parsed = {}
    unparsed = []
    for model in sorted(set(models)):
        routes, reason = parse_model(model)
        if routes is None:
            unparsed.append({"model": model, "family": family_of(model), "reason": reason})
            continue
        parsed[model] = {
            "family": family_of(model),
            "routes": routes,
        }
    return parsed, unparsed


def cross_check(parsed, unparsed):

    """Compare the pack with numbers hardcoded in railmancer/track.py."""

    notes = []

    radii = Counter()
    for entry in parsed.values():
        if entry["family"] != "arcs":
            continue
        radii[entry["routes"][0]["Radius"]] += 1

    extra = sorted(set(radii) - PATHFINDER_RADII)
    if extra:
        detail = ", ".join(f"{radius} ({radii[radius]} arcs)" for radius in extra)
        notes.append(
            "valid_next_tracks only offers radii "
            "2048, 3072, 4096, 6144, 8192. The pack also has "
            f"{detail}. Each extra radius is the base radius plus 192, "
            "the same 192-unit track spacing move_in_trackspace hardcodes, "
            "so those are the parallel-curve pieces and the pathfinder never offers them."
        )

    missing_radii = sorted(PATHFINDER_RADII - set(radii) - {0})
    if missing_radii:
        notes.append(
            "pathfinder radii with no arc in this pack: "
            + ", ".join(str(radius) for radius in missing_radii)
        )

    straight_dirs = Counter()
    slope_misses = []
    grade_misses = []
    for model, entry in parsed.items():
        if entry["family"] != "straights":
            continue
        route = entry["routes"][0]
        direction = route["StartDirection"]
        straight_dirs[direction] += 1
        change_x = -route["Move"][0]
        change_y = route["Move"][1]
        slope = STRAIGHT_SLOPE.get(direction)
        if slope is None or abs(change_x) < 1:
            continue
        expected_y = slope * change_x
        if abs(change_y - expected_y) > 1:
            slope_misses.append(
                f"{model}: Y {change_y} vs {expected_y} from move_in_trackspace"
            )
        if route["Length"]:
            gap = abs(route["RealGrade"] - route["ApproxGrade"])
            if gap > 0.2:
                grade_misses.append(
                    f"{model}: name grade {route['RealGrade']} vs rise/run {route['ApproxGrade']}"
                )

    if "4rt" not in straight_dirs:
        notes.append(
            "the pack has no 4rt straights (4lt is present). "
            "convert_length_to_mdl rewrites a 4rt request to 4lt, which matches the pack."
        )
    if slope_misses:
        notes.append(
            f"{len(slope_misses)} straights disagree with move_in_trackspace slopes. "
            + "; ".join(slope_misses[:5])
        )
    else:
        notes.append(
            "straight end-offsets match move_in_trackspace: "
            "0fw is flat in Y, 1rt/1lt are 1:4, 2rt/2lt are 1:2, 4lt is 1:1."
        )
    if grade_misses:
        notes.append(
            f"{len(grade_misses)} pieces whose pg token disagrees with ChangeZ/length by more than 0.2. "
            + "; ".join(grade_misses[:5])
        )

    present_lengths = set()
    for model, entry in parsed.items():
        if entry["family"] != "straights":
            continue
        route = entry["routes"][0]
        if route["StartDirection"] == "0fw" and route["RealGrade"] == 0:
            present_lengths.add(int(round(-route["Move"][0])))
    wanted = [32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2048, 3072, 4096, 6144, 8192]
    missing_lengths = [length for length in wanted if length not in present_lengths]
    if missing_lengths:
        notes.append(
            "decompose_length_to_straights asks for 0fw pieces that are not in the pack: "
            + ", ".join(str(length) for length in missing_lengths)
        )
    else:
        notes.append(
            "every straight length decompose_length_to_straights asks for exists as a flat 0fw piece."
        )

    families = Counter(entry["family"] for entry in parsed.values())
    if families.get("banked", 0) == 0:
        notes.append(
            "process_banked is unused by this pack revision: there is no banked/ folder."
        )

    unparsed_families = Counter(item["family"] for item in unparsed)
    if unparsed_families:
        summary = ", ".join(
            f"{family} {count}" for family, count in sorted(unparsed_families.items())
        )
        notes.append(
            "process_file has no reader for these track folders, so they are listed as unparsed: "
            + summary
            + "."
        )

    missing_route = [model for model in HAND_FIXED_ROUTE if model not in parsed]
    if missing_route:
        notes.append(
            "hand-fixed route pieces missing from the pack: " + ", ".join(missing_route)
        )
    else:
        notes.append(
            f"all {len(HAND_FIXED_ROUTE)} model names in the parallel-track "
            "hand-fixed route are in this pack and parse."
        )

    return notes


def build_manifest(source, models):

    parsed, unparsed = scan_models(models)
    counts = Counter(entry["family"] for entry in parsed.values())
    counts.update(item["family"] for item in unparsed)
    return {
        "source": source,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": dict(sorted(counts.items())),
        "parsed_count": len(parsed),
        "unparsed_count": len(unparsed),
        "cross_check": cross_check(parsed, unparsed),
        "unparsed": unparsed,
        "models": parsed,
    }


def write_manifest(manifest, path):

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")


def print_summary(manifest):

    source = manifest["source"]
    print(
        f"source {source.get('kind')} {source.get('commit', '')} "
        f"{source.get('commit_date', '')}"
    )
    print(
        f"parsed {manifest['parsed_count']}, "
        f"unparsed {manifest['unparsed_count']}"
    )
    for family, count in manifest["counts"].items():
        print(f"  {count:5} {family}")
    print("cross-check:")
    for note in manifest["cross_check"]:
        print(f"  - {note}")
    if manifest["unparsed_count"]:
        print("unparsed names:")
        for item in manifest["unparsed"]:
            print(f"  {item['model']}")


def main(argv=None):

    parser = argparse.ArgumentParser(description="Scan TrakPak3 track model names.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="rewrite the manifest from GitHub (names only)",
    )
    parser.add_argument(
        "--local",
        default="",
        help="scan this checkout or Steam trakpak3_rsg folder instead of GitHub",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print the manifest summary and cross-check, and do not write",
    )
    parser.add_argument("--output", default=MANIFEST_PATH)
    args = parser.parse_args(argv)

    if args.local or args.refresh:
        if args.local:
            source = local_source(args.local)
            models = list(iter_local_models(args.local))
            if not models:
                print(f"no trakpak3_rsg track models under {args.local}")
                return 1
        else:
            source, models = fetch_github_models()
        manifest = build_manifest(source, models)
        if not args.check:
            write_manifest(manifest, args.output)
            print(f"wrote {args.output}")
        print_summary(manifest)
        return 0

    if not os.path.exists(args.output):
        print(f"no manifest at {args.output}. Run with --refresh or --local.")
        return 1
    with open(args.output, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    print_summary(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
