# Parallel tracks: what was wrong, what the PR changes, and how to check it

This is the write-up for the parallel-track fix on `cursor/parallel-track-alignment-d5df` (pull request 1). It is not merged.

The ground truth for the real route is `c_fully_fixed.vmf`: 2 tracks on the left, 0 on the right, starting at the Vancouver node `(7568, 3552, -13040)`, direction `0fw`, heading `-90`. Isaiah fixed the straights in Hammer, including the two `2rt` fillers, and moved the end frog onto the rail. `check_track_vmf.py` reports **0 unpaired points** on that file. Regenerating the same backbone from this branch produces the same 99 pieces. Comparing endpoint pairs (not origins or angles) finds nothing in one set that is missing from the other. The six marker positions match too, including the end frog at `(12432, -13040, -11020)`.

## (a) How the problem was solved

A parallel run is two steps. Trackhammer walks one centerline piece at a time and records a node. Afterwards `write_track_from_trackhammer_steps` lays the center piece, the copies beside it, and the straight fillers that close the gaps.

The offset table and the step-over were already right. `get_offset_forward_for_parallel_on_right` still returns the hand-tuned pair for one track to the right, stored low angle to high angle. `get_addlength` is unchanged: if the piece is travelled high-angle to low-angle the signs flip, then each end is pushed forward by just enough that every filler length is zero or positive. `move_in_trackspace` is unchanged. Straights still contribute `(0, 0)`, so they tile. The spacing between tracks does not depend on radius.

What was wrong on `main` was where those fillers were drawn.

The exit filler was anchored on the far node. That node is already past the filler. The sideways step used the piece's end direction and `track + 1` (or `track - 1` when reversed), and the straight was drawn backwards (`yaw + 180`). So the filler started at the joint it was supposed to arrive at, ran the wrong way, and the side tracks did not land on the curve end. The entrance filler had the same backwards draw: it started at the curve origin and ran back along `Heading + 180`, instead of starting at the station and running forward to the curve.

Reversed pieces made that worse. The track index was mirrored (`tuple_to_range_list` with the reversed flag) and the prop was also yawed 180°. The yaw already flips prop-right into travel-left. Mirroring the index as well, then measuring the lateral from the far node, put the side tracks on the wrong rail whenever the heading had changed.

`4rt` has no straight model. `main` renamed the file to `4lt` and forced the Y sign negative, but left the prop at the node's heading. The mesh then followed the `4lt` diagonal, not the `4rt` step.

The rule this branch uses:

1. The backbone node is still his offset plus the push from `get_addlength`. Nothing there was rewritten for the families the table already lists.
2. For a forward piece, each track `t` in `-left .. +right` gets a forward gap and an exit gap from that same table. The curve origin is the start node, plus `move_in_trackspace(forward gap, incoming direction, t)`, rotated by the incoming heading.
3. If the forward gap is greater than 0, a straight runs from the station (the node plus only the lateral step) forward along the incoming direction for that many units.
4. If the exit gap is greater than 0, a straight runs from the curve's geometric far end forward along the exit direction. A zero gap places nothing.
5. A reversed piece is placed from the incoming station, not from the far node. The prop yaw is still plus 180. The track index is not mirrored again. The entrance shim runs from that station; the exit shim runs from the prop origin along the outgoing direction.
6. A `4rt` straight is the `4lt` model with yaw `heading - 90`. The origins are still stepped with `move_in_trackspace` in `4rt` space at the node's heading. `8lt` and `8rt` straights are `0fw` props; the heading carries the corner.
7. Every prop stays on the 16-unit grid. Lengths that are not in the straight list are decomposed into the existing lengths (32, 48, 64, 96, ...).

On the Vancouver route the curve endpoints were already the same in the raw file and in the fully fixed file. This branch's curve endpoints match that file. The straights that were scattered in the raw output now meet those curves, and the end frog sits on the main rail.

## (b) Diff against main, file by file

The shim and curve placement changes are in `railmancer/track.py`. `tools.py`, `railmancer.py`, `get_addlength`, `move_in_trackspace`, and `valid_next_tracks` are untouched. `trackhammer.py` inserts a ladder at a track-count change and does not change piece choice otherwise. The chooser is the same: `0fw` is not a stand-in for `8lt` or `8rt` when picking the next model. After an 8 piece the node direction is rewritten to `0fw`, which is what lets the next piece be chosen as `0fw`. Any `4` still chains with any other `4`, because the chooser compares the leading character.

New files, no effect on placement: `railmancer/joincheck.py`, `check_track_vmf.py`, `tests/test_parallel_geometry.py`, `tests/test_hand_fixed_route.py`, this file.

### `get_end_direction`

`main` compared the first character only, so `1lt` and `1rt` (and `2lt` / `2rt`, and the two 4s) counted as the same end. Entering a mirror curve from its end then asked `get_addlength` for a same-direction pair, which is `(0, 0)`, while the mesh was a real direction change. The filler length no longer matched the node.

Now an exact start returns the end, and an exact end returns the start. Only after that does a `4` match the other `4`. This changes the backbone gap for mirror entries. It does not change a same-hand curve entered from its authored start. On the fully fixed route the node positions come out the same as `main`.

### `get_new_node_from_node_and_model`

The 45° hand change used to take its hand from the authored start, and the whole jump (entrance filler, mesh, exit filler) was rotated by the new heading. An `8lt` / `8rt` exit then applied ±90 to the original heading, which dropped a 4-hand change that had happened on the same piece.

Now the hand is the end actually entered. When the heading changes by 45°, the entrance filler stays in the incoming heading and the mesh plus the exit filler use the turned heading. The 8's ±90 is applied on top of that turned heading. Reversed pieces and pieces with no heading change still rotate the whole jump by one heading, and a reversed mesh still uses `(MoveX, MoveY, -MoveZ)`.

This is behavior beyond the shims. A piece that both changes 4-hand and leaves through an 8 no longer loses the 4-hand turn. On the fully fixed route it does not move the nodes.

### `get_offset_forward_for_parallel_on_right`

The hand-tuned rows are the same numbers, for one track to the right, low angle then high angle. `get_addlength` still consumes them.

Three cases that used to return `(0, 0)` now go through `_grid_stagger` and `_snap_track_grid` (nearest multiple of 16):

- Same angle number, other hand (`1lt`↔`1rt`, `2lt`↔`2rt`, `4lt`↔`4rt`). `8lt`↔`8rt` is singular and snaps to `(0, 0)`.
- Both ends have a hand and the hands differ (`1lt`↔`4rt`, `1rt`↔`4lt`, and `1`↔`8` cross-hand). `main` applied the same-hand table row to those.
- A pair the table does not list. `main` printed `Invalid combination!` and returned `(0, 0)`.

Because `get_addlength` is the backbone push, these three cases move the next node, not only the filler. The families that are not an exact multiple of 16 are listed under residuals below.

### `straight_prop_yaw`, `create_straight`, `convert_length_to_mdl`

`create_straight` still decomposes the length and steps the origins with `move_in_trackspace` at the node's heading. The prop yaw is `straight_prop_yaw`: `heading - 90` when the direction is `4rt`, otherwise the heading.

`convert_length_to_mdl` turns `8lt` and `8rt` into a `0fw` filename, and turns `4rt` into `4lt` before it reads the Y step, so the filename is a real `4lt` piece (`+Lx-Lx`). `main` computed Y from the original direction and then forced the name to `4lt` with a minus sign, and it did not turn the prop.

### `write_track_from_trackhammer_steps`, `_place_reversed_piece`, `_travel_stagger`

This is the shim fix. The track count for a piece is the previous step's run (the count the backbone gap was computed with). Forward pieces use the rule in section (a): curve first, entrance shim from the station, exit shim from the curve's far end. The prop yaw for a piece that leaves through an 8 is the stored heading with that ±90 undone, because the stored heading is already the heading after the corner. Reversed adds 180 on top of that.

Every reversed piece goes through `_place_reversed_piece` and does not also run the forward loop. `_travel_stagger` is the same table, expressed in travel order (high-to-low flips the signs).

`main`'s far loop (`tracks_alt`, `track + 1`, `alt_heading + 180`) is gone. So is the entrance straight drawn backwards from the curve origin.

### What did not change

`valid_next_tracks` is untouched, so the pathfinder still chooses the same curves and straights. Grade limits, radius limits, and the block checks are the same. `move_in_trackspace` and `get_addlength` are the same functions as `main`. `trackhammer.py` only gained the ladder insertion described below. It does not change how a piece is chosen when the track count stays the same.

## (c) What is there now, and how to use it

### `check_track_vmf.py`

No flags. One argument, the VMF path.

```bash
python3 check_track_vmf.py path/to/map.vmf
```

Exit 0: every endpoint is shared by exactly two ends. If the file has no frog or cone, the open ends of a run may appear once, and they must be one `move_in_trackspace` step apart. Exit 1: a gap, a junction of three or more, a marker that misses the rail, or open ends that are not on that spacing. Exit 2: the path was omitted.

It does not read model bytes. Geometry comes from the TrackPack 3 name:

- The entity's `model` must contain `trakpak` and `/arcs/`, `/straights/`, `/banked/`, or `/switches/sidings/`. A `tp3_switch` entity is read the same way. Wyes, turnouts that are not sidings, and crossovers are skipped.
- A straight's direction is the second token (`s2048_0fw_...`). An arc's start is the first token without the leading `a`, and its end is the second token. Banked pieces drop the leading `ab`.
- The displacement token `+2048x00000x+064up` becomes `Move = [-2048, 0, 64]`. X in the name is mirrored because a 0-yaw prop points down -X. Z is the first four digits of the third component.
- The two endpoints are the origin, and the origin plus that Move rotated by the yaw. `rot_orth` only turns in 90° steps. A yaw that is not a multiple of 90 is truncated. Pitch and roll are ignored.
- The heading at each end is `get_heading` of that end's direction, rotated by the same yaw. Opposite headings count as the same joint, so a flipped prop still meets.

Frog (`frog.mdl`) and traffic cone (`trafficcone001a.mdl`) origins are endpoints. A marker on a track end adds one to that end's count, which is how an open end of a finished run becomes 2. A marker that is not on a track end is reported on its own. A marker on a point that has two different headings is reported as ambiguous.

A parallel siding counts as three endpoints: the point, the end of the main leg, and the end of the diverging leg. The point is one endpoint, not one per leg, so the rail that arrives there plus the switch is two. Both leg ends have to meet something else.

Limits: if the filename does not match what `process_file` or the siding parser expects, the script prints the model and exits 1. It will not notice a mesh that disagrees with its own filename. It will not check wyes or crossovers.

### Tests

There is no pytest file and no extra suite. These three scripts are the suite. They stub `turtle` themselves, because `lines.py` imports it and this environment has no Tk.

```bash
python3 tests/test_parallel_geometry.py
python3 tests/test_hand_fixed_route.py
python3 tests/test_switch_ladders.py
```

`test_parallel_geometry.py` builds synthetic arcs (no real mdl files) and checks every grid-legal direction change, both directions through the piece, headings 0/90/180/270, and every track count from 0 to 3 on each side. Consecutive pieces have to meet in position and heading. At each backbone node, track `t` has to sit on `move_in_trackspace`'s lateral for `t`. It also checks that the hand-tuned table did not drift. The run prints the case count, the failure count, and the rounded-stagger residuals. Last run on this branch: **8452 exact-join cases, 0 failures**.

`test_hand_fixed_route.py` rebuilds the fully fixed route. The backbone model list is the center track from that VMF, in order, with mode `(2, 0)` and the Vancouver start node. It asserts:

- the endpoint pair of every generated prop equals `EXPECTED_PIECES`, which was copied from `c_fully_fixed.vmf` (99 pairs, curves and straights)
- the six frog and cone positions in `EXPECTED_MARKERS` each land on a track end, including the end frog at `(12432, -13040, -11020)`
- the ordinary joint hash, with the run's open ends allowed, reports nothing

A flipped prop passes, because each pair is sorted. A moved origin or a changed angle fails when the endpoints move.

### Checking a new route

```bash
python3 check_track_vmf.py path/to/map.vmf
```

Read `unpaired points`. 0 means every rail end and every frog or cone meets something. A count of 1 is a gap or an open end. A count of 3 or more is three rails on one point. The lines under `problems:` name the position and the heading.

### Adding a regression from a hand-fixed VMF

1. Run the checker on the hand-fixed file and keep it only if the unpaired count is 0, or the only singles are the real open ends.
2. Walk the center track and write down the backbone models in order (the graded straights and the arcs, not the 0-grade shims). Note the start node and the `(left, right)` mode.
3. Put that list, the start node, and the mode into a copy of `tests/test_hand_fixed_route.py`.
4. Generate once, print each prop's two endpoints with `prop_endpoints` in `railmancer/joincheck.py`, sort the pair, and store them. Store frog and cone origins the same way.
5. The assertion compares those sets. Do not compare origin or yaw. Re-run the script. It exits 1 if any endpoint is only in the file or only in the generated route.

### Residuals

Some direction pairs cannot meet exactly on the 16-unit grid. The geometry test prints the distance from a perfect joint. Outermost of 3 tracks on each side:

| pair | per track | at 3 tracks |
| --- | --- | --- |
| `1`↔`8` | 4 | 12 |
| `1lt`↔`4rt` and `1rt`↔`4lt` | 4 | 12 |
| `8lt`↔`8rt` | 384 | 1152 |

`1`↔`8` and the crossed `1`↔`4` pairs have an exact stagger that is not a multiple of 16 (about 4 units per track). `_snap_track_grid` rounds each component to the nearest 16, which is the closest the props can sit. Closing them exactly means leaving the 16-grid, and the straight models are not authored that way. A kinked filler, not collinear with either tangent, would be a different design.

`8lt`↔`8rt` is worse. The two forwards point the same way in world space (both are 90° corners, opposite hands), so no pair of straight lengths can cancel the sideways step. That step is 384 units in X per track. The snap is `(0, 0)`, and the side track stays 384 off per track. A straight shim cannot fix it. It needs a curve between those two directions, or the pathfinder has to stop offering that pair as a straight-shim joint.

### Switch ladders

A ladder is added wherever the parallel count changes. Nothing in the offset table or the shim writer was replaced. `trackhammer.py` notices that the next chosen piece would pass a run boundary whose track count differs. If a shorter piece still fits before that boundary, it keeps looking. If nothing fits, it fills the gap with a level tangent straight (rounded up to the grid step for that direction) and then reserves the ladder. The ladder is flat: Z does not change. There is no flag to turn this off. Crossovers are not built.

The hand comes from which side gained or lost tracks. The model is the condensed parallel siding of that direction and hand: the diverging leg is longer than the main leg, and both ends sit on `move_in_trackspace`. Extended sidings, where the two legs are the same length, are in the catalog and are not used. The catalog is `data/trakpak3_models.json`, a list of model paths. Lengths are not stored there. `geometry_from_model` reads the filename. The sibling branch `cursor/scored-track-selection-deec` did not have a scanner when this was written, so this list is the sparse catalog that scanner can replace later.

Chosen models, smallest condensed siding that lands on the grid. Every one of these has main length 768 and diverging length 1536:

| direction | hand | file |
| --- | --- | --- |
| `0fw` | left | `p0fw_left_minr2048_+0768x00000_+1536x-0192_dv.mdl` |
| `0fw` | right | `p0fw_right_minr2048_+0768x00000_+1536x+0192_dv.mdl` |
| `1lt` | left | `p1lt_left_minr2048_+0768x-0192_+1488x-0576_dv.mdl` |
| `1lt` | right | `p1lt_right_minr2048_+0768x-0192_+1584x-0192_dv.mdl` |
| `1rt` | left | `p1rt_left_minr2048_+0768x+0192_+1584x+0192_dv.mdl` |
| `1rt` | right | `p1rt_right_minr2048_+0768x+0192_+1488x+0576_dv.mdl` |
| `2lt` | left | `p2lt_left_minr3072_+0768x-0384_+1440x-0960_dv.mdl` |
| `2lt` | right | `p2lt_right_minr3072_+0768x-0384_+1632x-0576_dv.mdl` |
| `2rt` | left | `p2rt_left_minr3072_+0768x+0384_+1632x+0576_dv.mdl` |
| `2rt` | right | `p2rt_right_minr3072_+0768x+0384_+1440x+0960_dv.mdl` |

On a slope the larger filename component is not the along-track length. `p1lt_left` diverges `+1488x-0576`, and 1488 is the larger component, but that point is `move_in_trackspace(1536, "1lt", -1)`. The 1536 is what the ladder steps. For `0fw` the larger component and the station are the same number.

How one ladder is built, for N switches on the left and none on the right. The zone is `N * 1536` long.

1. Switch 0 sits on the current outermost left track, at the start of the zone. Its main leg runs 768 along that track. Its diverging leg ends 1536 ahead and one track further left.
2. Switch 1 sits on that diverging end. Same pattern. The next switch's point is the previous diverging end, so those two endpoints meet with nothing between them.
3. The last diverging end is the end of the zone, on the new outer track. No filler past it.
4. Every other track that already existed gets a straight for the whole zone. A track that holds a switch gets a straight only for the part the main leg does not cover: zone minus the stations already taken. That is the owner's fill: main gets `total - short`, the next track gets `total - long - short`, and the last track is just the long leg.

A merge is that ladder run backwards. The points sit at the far end, the heading is plus 180, and the model is the opposite hand, which puts the diverging leg back on the side that is going away. Filler straights still run forward in the direction of travel.

Both sides at once, from a single track (`0L0R -> 1L1R`), share the root. The side with more switches goes first. The other side's first switch starts at the end of that first main leg (768), so the two switches do not stack on one point. When both sides add the same number, the zone is `N * 1536 + 768`. `3L0R -> 0L3R` is not that. It is two zones in a row: merge all three left tracks into the main, then split three right tracks off the main. `_phases` is the list that sets that order.

One Hammer entity, `tp3_switch`, carries the `_mn` model and the `_dv` model. The checker counts that entity as three endpoints. `create_straight` now raises if the length is negative or not a multiple of 16. A 1-in-4 filler also has to be a multiple of 64, and a 1-in-2 filler a multiple of 32, or the sideways step leaves the 16-grid. The pathfinder rounds the gap fill up to that step.

A side that is ending and a side that is starting share one zone. `3L0R -> 0L3R` used to be a full left merge and then a full right split, placed end to end. The merge ladder is now the same ladder run backwards in the same stretch the split occupies, so the zone is as long as the longer ladder instead of the sum. `0L0R -> 1L1R` was already one shared zone: both switches cannot sit on the same point, so the second starts at the end of the first main leg (768). That length did not get shorter. `2L1R -> 1L2R` did.

The whole corridor, every parallel track, is bounds-checked before the fill or the zone is accepted. A corridor that leaves the border or hits a block is rejected and the pathfinder backtracks, the same way a normal piece is rejected.

Each run can say how it joins the previous one. The key sits in the run's parameter dict in `railmancer.py`. Leave it out and every side gets switches, which is the old behavior.

```python
[
    [(0, 0), 0.3, {"min_radius": 5, "min_grade": 0, "max_grade": 0}],
    [(3, 0), 1.0, {"min_radius": 2, "min_grade": 3, "max_grade": 3, "join": "switch"}],
    [(0, 3), 1.0, {"min_radius": 2, "min_grade": 3, "max_grade": 3, "join": {"left": "stub", "right": "switch"}}],
]
```

`"stub"` on a side means those tracks just end or begin. Their endpoints stay unpaired, which the checker already allows at a run end. A per-track list would punch a hole in the ladder, because each switch's diverging end is the next switch's point, so the control is per side.

As a run gets close to its length, pieces that would leave no room for the upcoming zone are skipped, and the gap in front of the zone is filled with a grid-snapped straight that does not round past the target. `trackhammer_fit_run_length` in `config.json` turns that off if you want the old "fill whatever is left, then add the zone" behavior. It works with the scored selector and with height mode, because the corridor check uses the same block test as a normal piece.

`4lt` and `4rt` sidings do not land on a parallel track. The condensed `4lt` diverging point is 32 units off `move_in_trackspace`. There is no `4rt` siding and no `8lt` / `8rt` siding. A run boundary in those directions does not get a ladder; the pathfinder prints the error and tries another piece. After an 8 piece the node direction is already `0fw`, so the boundary after a corner is a normal `0fw` ladder. A boundary while the train is still on `4lt` or `4rt` is unsolved.

```bash
python3 tests/test_switch_ladders.py
```

That run is 84 transitions (the count changes in the owner's list, both hands, on `0fw`, `1lt`, `2lt`, and `2rt`, at several headings) plus the writer hook, the length guards, and the model check. Latest run: **0 failures**. The other two scripts are unchanged: **8452** geometry cases, **0 failures**, and the fully fixed route **99 pieces, 6 markers, 0 failures**.

### A full Railmancer run

```bash
python3 railmancer.py
```

That is the normal entry point. On this machine it stops at import:

```text
ModuleNotFoundError: No module named 'noise'
```

`heightmap.py` imports `pnoise3` from the `noise` package. Building that package here fails because `Python.h` is not installed. Past that, `lines.py` imports `turtle` (no Tk in this environment), the track library path in `railmancer.py` is a Windows Steam directory that is not on this machine, and `vmf inputs/vancouver_only.vmf` is not in the repo. The three scripts above are the runs that actually execute here. They do not need the mdl files, that VMF, or the noise package.

The numbers from the latest run of those scripts, and of the checker on `c_fully_fixed.vmf`, are in the pull request description.
