"""Machine paths for the scripts. Map numbers stay in config.json.

Lookup order for each key:

1. The environment variable named below, when it is set and not empty.
2. The same key in railmancer/settings.local.json, which is gitignored.
3. The default in this file.

The defaults are the paths Isaiah's machine already uses, so a checkout
with no local file and no variables runs the same way it did before.
Copy settings.example.json to settings.local.json to point the scripts
somewhere else. The example file lists the same defaults.
"""

import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_PATH = os.path.join(_DIR, "settings.local.json")

# Kept equal to settings.example.json. tests/test_settings.py checks that.
DEFAULTS = {
    "track_library": (
        "C:/Program Files (x86)/Steam/steamapps/common/GarrysMod/"
        "garrysmod/addons/trakpak/models/trakpak3_rsg"
    ),
    "vmf_input": "vmf inputs/vancouver_only.vmf",
    "vmf_output_dir": "C:/Users/Metaladon/Desktop/Model Data/VMFS/railmancer",
    "switchstands_track_library": (
        "C:/Program Files (x86)/Steam/steamapps/common/"
        "Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
    ),
    "switchstands_vmf_input": "vmf inputs/hb_terminal_track.vmf",
}

ENV = {
    "track_library": "RAILMANCER_TRACK_LIBRARY",
    "vmf_input": "RAILMANCER_VMF_INPUT",
    "vmf_output_dir": "RAILMANCER_VMF_OUTPUT_DIR",
    "switchstands_track_library": "RAILMANCER_SWITCHSTANDS_TRACK_LIBRARY",
    "switchstands_vmf_input": "RAILMANCER_SWITCHSTANDS_VMF_INPUT",
}


def _read(path):

    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {path}: {exc}")
        return {}
    if not isinstance(loaded, dict):
        print(f"Could not read {path}: expected an object of path strings.")
        return {}
    return loaded


def get(key):

    env_name = ENV[key]
    override = os.environ.get(env_name)
    if override:
        return override
    local = _read(LOCAL_PATH).get(key)
    if local not in (None, ""):
        return local
    return DEFAULTS[key]
