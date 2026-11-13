# TrakPak3 model scanner

Railmancer reads track geometry from the model **filename**, not from the `.mdl` bytes. `tools/scan_trakpak3.py` lists those names and runs them through `railmancer.track.process_file`, the same parser `build_track_library` uses.

The result is committed at `data/trakpak3_models.json`. Tests and `benchmark_trackhammer` load that file, so a normal run needs no network and no Steam install.

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

## Use it from the benchmark

Real pieces are the default:

```
python -m railmancer.benchmark_trackhammer
```

The old synthetic library is still there:

```
python -m railmancer.benchmark_trackhammer --library synthetic
```

## Consolidate fragmented straights

`tools/consolidate_vmf_straights.py` rewrites adjacent straight props into longer stock pieces (same lengths / grade tokens as the straight generator). Railmancer also calls `consolidate_straights.consolidate_inplace()` before the final VMF write.

```
python3 tools/consolidate_vmf_straights.py map.vmf
python3 tools/consolidate_vmf_straights.py map.vmf --smooth-grade -o map_merged.vmf
python3 check_track_vmf.py map_consolidated.vmf
```

Without `--smooth-grade`, flat (`0pg`) runs and each graded token run merge separately. With it, collinear same-direction straights may mix grade versions so the total rise still matches the original endpoints.
