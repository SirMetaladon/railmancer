# railmancer
Python script for procedurally generating railroad route VMF's for use in Garry's Mod

Machine paths are not in the scripts. Copy `railmancer/settings.example.json` to `railmancer/settings.local.json` (gitignored) or set `RAILMANCER_TRACK_LIBRARY`, `RAILMANCER_VMF_INPUT`, `RAILMANCER_VMF_OUTPUT_DIR`, `RAILMANCER_SWITCHSTANDS_TRACK_LIBRARY`, and `RAILMANCER_SWITCHSTANDS_VMF_INPUT`. With neither, the scripts use the paths on Isaiah's machine.

`python3 railmancer.py` is the map. `python3 switchstands.py` is the switch-stand pass. `python3 check_wall_clearance.py path/to/map.vmf` fits and links sectors for that file and prints centerline distance to the nearest wall. Handmade samples whose nearest wall is the sector-grid edge are omitted, and that count is printed. Tests: `python3 -W error::DeprecationWarning -m unittest discover -s tests`.