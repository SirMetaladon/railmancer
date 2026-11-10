"""Headless old-vs-new comparison for trackhammer's candidate search.

railmancer.py itself will not run here: it imports turtle, the noise
package, a Windows Steam copy of TrackPack 3, and a VMF that is not in
the repo. This module installs a synthetic library of straights and arcs
that follow the same direction, radius, and grade-level rules, and it
replaces the square map edge with a rectangle or an L.

From the repo root:

    python -m railmancer.benchmark_trackhammer
    python -m unittest tests.test_trackhammer_score -v

Turn the scored search on for a real map by setting
trackhammer_scored_selection to 1 in railmancer/config.json, then run
python railmancer.py the way you already do. Weights are in that same
file. Grade weight is points per 1.0 of extra rise/run, so 100 charges
one point for each extra percent of grade. Runway weight is points per
probe cell that is not clear. Hug weight is subtracted for each side
that touches the border or a lower track layer. Heading weight is points
per 90 degrees. Reverse weight is a flat charge for flipping a curve
from left to right or the other way. Jitter is a random 0..weight added
so similar pieces do not always tie.

The default run asks for 2.5 miles inside a small border, which is long
enough that a low grade has to fold instead of shooting across once. The
attempt limit here is 12000 failed placements. A home run uses whatever
trackhammer_attempt_limit is in the config (250000 unless you change it).
Three seeds, both shapes, both selectors, and both block modes (layers and
height) take several minutes because the scored search prices every legal
piece at every step. Height mode stores one rail height per cell and clears
trackhammer_height_clearance (one sector_minimum_height) instead of two
block layers.

One existing footgun shows up in the 0..1 band: valid_next_tracks skips
its minimum-grade test when min_grade is 0, because `0 != False` is
false in Python. That band therefore still allows descending pieces.
"""

import argparse
import contextlib
import io
import math
import random
import time

from railmancer import cfg, tools, track, trackhammer

BODY = ["4lt", "2lt", "1lt", "0fw", "1rt", "2rt", "4rt"]
# Positive bands only. Negative pieces exist in real TrackPack, but a 4-direction
# model is signed backwards by valid_next_tracks and not by placement, so a
# downhill 45-degree straight sneaks into a climbing band. Leaving those out
# keeps this harness on the grade the run actually asked for.
GRADES = (0.0, 1.2, 2.2, 3.2)
STRAIGHT_LENGTHS = (1024, 2048)
NOTCH_RADII = (2048, 4096, 8192)
QUARTER_RADII = (2048, 4096)

# Benchmark world. Block size stays on the config value (2000 after the
# existing clamp) so clearance and the probe match a home run.
RECT_HALF_X = 12000
RECT_HALF_Y = 8000
L_OUTER = 12000
L_INNER = 2000
TARGET_MILES = 2.5
ATTEMPT_LIMIT = 12000
SEEDS = (1, 2, 3)
GRADE_BANDS = ((3, 3), (1, 2), (0, 1))


def yaw_components(direction, distance):

    angle = math.radians(180.0 + track.direction_to_angle(direction))
    return math.cos(angle) * distance, math.sin(angle) * distance


def straight_move(direction, length, grade_percent):

    mx, my = yaw_components(direction, length)
    dz = (grade_percent / 100.0) * length
    return (mx, my, dz), length


def curve_move(start_dir, end_dir, radius, grade_percent):

    a0 = track.direction_to_angle(start_dir)
    a1 = track.direction_to_angle(end_dir)
    sweep = a1 - a0
    arc = radius * math.radians(abs(sweep))
    steps = 48
    x = 0.0
    y = 0.0
    ds = arc / steps
    for i in range(steps):
        angle = a0 + sweep * ((i + 0.5) / steps)
        rad = math.radians(180.0 + angle)
        x += math.cos(rad) * ds
        y += math.sin(rad) * ds
    horiz = math.hypot(x, y) or 1.0
    dz = (grade_percent / 100.0) * horiz
    return (x, y, dz), arc


def register_piece(name, start, end, radius, length, move, grade_percent):

    track.track_model_library[name] = {
        "Length": float(length),
        "Radius": int(radius),
        "StartDirection": start,
        "EndDirection": end,
        "GradeLevel": track.determine_grade_level(float(grade_percent)),
        "Move": [float(move[0]), float(move[1]), float(move[2])],
        "ApproxGrade": float(grade_percent),
        "RealGrade": float(grade_percent),
    }


def install_mainline_library():

    track.track_model_library.clear()
    track.valid_tracks_cache.clear()

    for direction in BODY:
        for length in STRAIGHT_LENGTHS:
            for grade in GRADES:
                move, reported = straight_move(direction, length, grade)
                register_piece(
                    f"syn/s/{direction}/{length}/{grade}",
                    direction,
                    direction,
                    0,
                    reported,
                    move,
                    grade,
                )

    for index in range(len(BODY) - 1):
        left = BODY[index]
        right = BODY[index + 1]
        for start, end in ((left, right), (right, left)):
            for radius in NOTCH_RADII:
                for grade in GRADES:
                    move, arc = curve_move(start, end, radius, grade)
                    register_piece(
                        f"syn/c/{start}_{end}/r{radius}/{grade}",
                        start,
                        end,
                        radius,
                        arc,
                        move,
                        grade,
                    )

    quarters = [
        ("4lt", "8lt"),
        ("2lt", "8lt"),
        ("1lt", "8lt"),
        ("0fw", "8lt"),
        ("0fw", "8rt"),
        ("1rt", "8rt"),
        ("2rt", "8rt"),
        ("4rt", "8rt"),
    ]
    for start, end in quarters:
        for radius in QUARTER_RADII:
            for grade in GRADES:
                move, arc = curve_move(start, end, radius, grade)
                register_piece(
                    f"syn/q/{start}_{end}/r{radius}/{grade}",
                    start,
                    end,
                    radius,
                    arc,
                    move,
                    grade,
                )

    return len(track.track_model_library)


def rectangle_border(half_x, half_y):

    def inside(point):
        x, y = point
        return abs(x) < half_x and abs(y) < half_y

    return inside


def l_border(outer, inner):

    # Horizontal bar along the bottom, vertical bar up the left side.
    def inside(point):
        x, y = point
        horizontal = abs(x) < outer and -outer < y < -inner
        vertical = -outer < x < -inner and abs(y) < outer
        return horizontal or vertical

    return inside


def shape_setup(name):

    if name == "rectangle":
        predicate = rectangle_border(RECT_HALF_X, RECT_HALF_Y)
        start = [9000, 0, 0]
    elif name == "l":
        predicate = l_border(L_OUTER, L_INNER)
        start = [8000, -7000, 0]
    else:
        raise ValueError(name)
    return predicate, [start, "0fw", 0, False]


def cells_used(steps):

    used = set()
    for step in steps:
        points = list(step.get("points") or [])
        node = step.get("node")
        if node:
            position = node[0]
            if position is not None and not isinstance(position, str):
                points.append(position)
        for point in points:
            try:
                block_ids = trackhammer.get_block_ids(point)
            except Exception:
                continue
            for block_id in block_ids:
                x, y, _z = block_id.split(",")
                cell = (int(x), int(y))
                if cell in trackhammer.BorderDistance:
                    used.add(cell)
    return used


def run_case(
    mode, seed, shape, grade_band, target_miles, attempt_limit, block_mode="layers"
):

    predicate, start = shape_setup(shape)
    cfg.CFG["trackhammer_scored_selection"] = 1 if mode == "new" else 0
    cfg.CFG["trackhammer_block_mode"] = block_mode
    cfg.CFG["trackhammer_height_direction"] = "up"
    cfg.CFG["trackhammer_attempt_limit"] = int(attempt_limit)
    trackhammer.set_border_override(predicate)
    trackhammer.rebuild_border_distance()
    trackhammer.clear_occupied()
    trackhammer.debug_overall_count = 0
    trackhammer.logLength = 0
    random.seed(seed)

    profile = trackhammer.aggregate_track_profile(
        [
            [
                (0, 0),
                target_miles,
                {
                    "min_radius": 0,
                    "min_grade": grade_band[0],
                    "max_grade": grade_band[1],
                },
            ]
        ]
    )
    target = profile[-1][1]
    inside = len(trackhammer.BorderDistance)
    started = time.perf_counter()
    logs = io.StringIO()
    with contextlib.redirect_stdout(logs):
        steps = trackhammer.create_rail_path(start, profile)
    elapsed = time.perf_counter() - started

    steps = steps or []
    if steps:
        length = float(steps[-1]["length"])
        end_z = float(steps[-1]["node"][0][2])
    else:
        length = 0.0
        end_z = float(start[0][2])
    rise = end_z - float(start[0][2])
    used = cells_used(steps)
    stats = dict(trackhammer.search_stats)
    finished = length + 1e-6 >= target and not stats["died"] and not stats["stuck"]
    return {
        "mode": mode,
        "blocks": block_mode,
        "seed": seed,
        "shape": shape,
        "band": f"{grade_band[0]}..{grade_band[1]}",
        "miles": length / 63360.0,
        "rise": rise,
        # A few dozen units over a mile is flat. Dividing by that prints a
        # nonsense ratio, so only report length/rise once the rise is real.
        "per_rise": (length / rise) if abs(rise) > 100.0 else None,
        "coverage": (len(used) / inside) if inside else 0.0,
        "died": int(stats["died"] or not finished and not stats["stuck"]),
        "stuck": int(stats["stuck"]),
        "attempts": int(stats["attempts"]),
        "score_checks": int(stats["score_checks"]),
        "pops": int(stats["one_step_pops"]),
        "rewinds": int(stats["distance_backtracks"]),
        "seconds": elapsed,
        "finished": finished,
    }


def _fmt(value, digits):

    if value is None:
        return f"{'flat':>{digits}}"
    return f"{value:{digits}.3f}"


def print_table(rows):

    header = (
        f"{'shape':<10} {'band':<7} {'mode':<4} {'blocks':<7} {'seed':>4} "
        f"{'miles':>7} {'rise':>8} {'len/rise':>8} {'cover':>6} "
        f"{'died':>4} {'stuck':>5} {'tried':>7} {'sec':>7}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['shape']:<10} {row['band']:<7} {row['mode']:<4} {row['blocks']:<7} {row['seed']:>4} "
            f"{row['miles']:>7.3f} {row['rise']:>8.1f} {_fmt(row['per_rise'], 8)} "
            f"{row['coverage']:>6.3f} {row['died']:>4} {row['stuck']:>5} "
            f"{row['attempts']:>7} {row['seconds']:>7.2f}"
        )


def print_summary(rows):

    groups = {}
    for row in rows:
        key = (row["shape"], row["band"], row["mode"], row["blocks"])
        groups.setdefault(key, []).append(row)

    print()
    print(
        f"{'shape':<10} {'band':<7} {'mode':<4} {'blocks':<7} {'n':>2} "
        f"{'miles':>7} {'rise':>8} {'len/rise':>8} {'cover':>6} "
        f"{'died':>4} {'stuck':>5} {'tried':>7} {'sec':>7}"
    )
    for key in groups:
        items = groups[key]
        n = len(items)

        def avg(name):
            return sum(item[name] for item in items) / n

        ratios = [item["per_rise"] for item in items if item["per_rise"] is not None]
        # One descending seed must not stand in for a group that was mostly flat.
        ratio = sum(ratios) / len(ratios) if ratios and len(ratios) * 2 >= n else None
        shape, band, mode, blocks = key
        print(
            f"{shape:<10} {band:<7} {mode:<4} {blocks:<7} {n:>2} "
            f"{avg('miles'):>7.3f} {avg('rise'):>8.1f} {_fmt(ratio, 8)} "
            f"{avg('coverage'):>6.3f} {sum(i['died'] for i in items):>4} "
            f"{sum(i['stuck'] for i in items):>5} {avg('attempts'):>7.0f} "
            f"{avg('seconds'):>7.2f}"
        )


def self_check():

    node = ([0, 0, 0], "0fw", 0, False)
    model = "syn/s/0fw/1024/0.0"
    result = trackhammer.iterate_backbone(model, node, (0, 0))
    if result is None:
        raise RuntimeError("synthetic straight was rejected at the origin")
    moved = float(result[0][0][0])
    if not moved < -500:
        raise RuntimeError(f"straight did not travel -X, ended at x={moved}")
    quarter = "syn/q/0fw_8rt/r2048/0.0"
    turned = trackhammer.iterate_backbone(quarter, node, (0, 0))
    if turned is None:
        raise RuntimeError("quarter turn was rejected at the origin")
    if turned[0][1] != "0fw" or int(turned[0][2]) != -90:
        raise RuntimeError(
            f"quarter turn did not yaw to 0fw/-90, got {turned[0][1:3]}"
        )


def main(argv=None):

    parser = argparse.ArgumentParser(description="Compare trackhammer selectors.")
    parser.add_argument("--miles", type=float, default=TARGET_MILES)
    parser.add_argument("--attempt-limit", type=int, default=ATTEMPT_LIMIT)
    parser.add_argument("--seeds", type=int, nargs="*", default=list(SEEDS))
    args = parser.parse_args(argv)

    cfg.initialize("railmancer/config.json")
    # Scored weights stay at the config defaults. The flag is flipped per run.
    cfg.CFG["trackhammer_scored_selection"] = 0
    trackhammer.initialize()
    count = install_mainline_library()
    # initialize() builds the square field; the cases below replace it.
    self_check()
    print(f"Synthetic library: {count} pieces. Block {trackhammer.BlockHorizontal} x {trackhammer.BlockVertical:.0f}.")
    print(
        "Weights "
        f"grade={cfg.CFG['trackhammer_score_weight_grade']} "
        f"runway={cfg.CFG['trackhammer_score_weight_runway']} "
        f"hug={cfg.CFG['trackhammer_score_weight_hug']} "
        f"heading={cfg.CFG['trackhammer_score_weight_heading']} "
        f"reverse={cfg.CFG['trackhammer_score_weight_reverse']} "
        f"jitter={cfg.CFG['trackhammer_score_weight_jitter']} "
        f"K={cfg.CFG['trackhammer_score_top_k']} "
        f"probe={cfg.CFG['trackhammer_score_probe_cells']} "
        f"pop_limit={cfg.CFG['trackhammer_score_pop_limit']}"
    )
    print(
        f"Target {args.miles} miles, attempt cap {args.attempt_limit} "
        f"(config default is {250000}). "
        f"Height clearance {cfg.CFG['trackhammer_height_clearance']}."
    )

    rows = []
    for shape in ("rectangle", "l"):
        for band in GRADE_BANDS:
            for seed in args.seeds:
                for mode in ("old", "new"):
                    for block_mode in ("layers", "height"):
                        row = run_case(
                            mode,
                            seed,
                            shape,
                            band,
                            args.miles,
                            args.attempt_limit,
                            block_mode,
                        )
                        rows.append(row)
                        print(
                            f"done {shape} {band[0]}..{band[1]} seed {seed} {mode} {block_mode}: "
                            f"{row['miles']:.3f} mi, cover {row['coverage']:.3f}, "
                            f"died {row['died']}, stuck {row['stuck']}, "
                            f"{row['seconds']:.2f}s",
                            flush=True,
                        )

    print()
    print_table(rows)
    print_summary(rows)
    return rows


if __name__ == "__main__":
    main()
