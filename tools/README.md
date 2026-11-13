# TrakPak3 model scanner

Railmancer reads track geometry from the model **filename**, not from the `.mdl` bytes. `tools/scan_trakpak3.py` lists those names and runs them through `railmancer.track.process_file`, the same parser `build_track_library` uses.

The result is committed at `data/trakpak3_models.json`. Tests load that file, so a normal run needs no network and no Steam install.

## Refresh from GitHub

This asks the GitHub tree API for filenames only. It does not download models, materials, or physics meshes.

```
python tools/scan_trakpak3.py --refresh
```

## Scan a local copy

The same folder `railmancer.py` already uses works. Point `--local` at a checkout, an addon, or the Steam `trakpak3_rsg` directory:

```
python tools/scan_trakpak3.py --local "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Singleplayer/ep2/custom/trakpak/models/trakpak3_rsg"
```

If that directory is inside a git checkout, the manifest records `HEAD`.

## Read the current manifest

```
python tools/scan_trakpak3.py --check
```

That prints counts by family, every name `process_file` could not parse, and the cross-check against hardcoded radii, straight slopes, and the hand-fixed route model list.

## Tests that load it

```
python -m unittest tests.test_trakpak_scan -v
python3 tests/test_switch_ladders.py
```
