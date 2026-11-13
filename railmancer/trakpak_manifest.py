"""Load the committed TrakPak3 manifest into the track library.

The manifest is names and parsed fields only. Railmancer never needs the
.mdl bytes. Regenerate it with tools/scan_trakpak3.py --refresh.
"""

import json
import os

from railmancer import track

DEFAULT_MANIFEST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "trakpak3_models.json",
)


def load_manifest(path=None):

    path = path or DEFAULT_MANIFEST
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def install_manifest_library(path=None):

    """Put single-route pieces into track.track_model_library.

    Same rule as track.build_track_library: a switch has two routes, so it
    stays out of the pathfinder. Straights, arcs, and banked pieces go in.
    """

    manifest = load_manifest(path)
    track.track_model_library.clear()
    track.valid_tracks_cache.clear()
    track.track_straight_cache.clear()

    installed = 0
    for model, entry in manifest["models"].items():
        routes = entry.get("routes") or []
        if len(routes) != 1:
            continue
        track.track_model_library[model] = routes[0]
        installed += 1
        if entry.get("family") == "straights":
            change_x = int(round(-routes[0]["Move"][0]))
            direction = routes[0]["EndDirection"]
            grade = routes[0]["GradeLevel"]
            key = f"{change_x}|{direction}"
            bucket = track.track_straight_cache.setdefault(key, {})
            bucket[grade] = model

    return installed
