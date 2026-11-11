"""Switch ladders between parallel runs.

A ladder is inserted wherever the track count changes. The offset table,
step-over, and straight shims are unchanged. This module only adds the
level tangent zone those pieces already know how to leave and enter.

Switch geometry comes from TrackPack 3 parallel-siding filenames. The
condensed models (diverging leg longer than the main leg) are the ones
used. Extended models, where both legs are the same length, are ignored.
"""

import json
import os

from railmancer import track, vmfpy

_CATALOG = None
_PARSED = None


class SwitchGeometryError(LookupError):
    """No condensed siding in this direction lands on the parallel grid."""


def _catalog_path():

    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "data", "trakpak3_models.json")


def catalog_models():

    global _CATALOG
    if _CATALOG is None:
        with open(_catalog_path(), "r", encoding="utf-8") as handle:
            _CATALOG = json.load(handle)["models"]
    return list(_CATALOG)


def _token_pair(token):

    # "+0768x-0192" or "+0768x00000"
    left, right = token.split("x")
    return int(left), int(right)


def _solve_leg(change_x, change_y, direction):

    """Station and track index whose step is this filename displacement.

    Filenames store hammer offsets. Railmancer's model space mirrors X,
    which is the same convention as every other piece: Move = [-ChangeX,
    ChangeY, 0]. The along-track length is the station s where that Move
    equals move_in_trackspace(s, direction, t). For a 0fw piece that s is
    the larger component. On a slope the larger component is not s, because
    the parallel step is diagonal, so s is solved rather than assumed.
    """

    target = (-change_x, change_y)
    for tracks in range(-4, 5):
        for station in range(0, 8192 + 16, 16):
            step = track.move_in_trackspace(station, direction, tracks)
            if abs(float(step[0]) - target[0]) < 1e-6 and abs(float(step[1]) - target[1]) < 1e-6:
                return station, tracks
    return None


def geometry_from_model(model_path):

    """Both legs of one siding, inferred from its filename."""

    name = model_path.replace("\\", "/").rsplit("/", 1)[-1]
    if name.endswith("_mn.mdl"):
        name = name[: -len("_mn.mdl")] + "_dv.mdl"
    stem = name[: -len(".mdl")] if name.endswith(".mdl") else name
    if stem.endswith("_dv"):
        stem = stem[: -len("_dv")]
    parts = stem.split("_")
    # p0fw_left_minr2048_+0768x00000_+1536x-0192
    direction = parts[0][1:]
    hand = parts[1]
    radius = int(parts[2].replace("minr", ""))
    main_x, main_y = _token_pair(parts[3])
    div_x, div_y = _token_pair(parts[4])
    main = _solve_leg(main_x, main_y, direction)
    diverging = _solve_leg(div_x, div_y, direction)
    exact = (
        main is not None
        and diverging is not None
        and main[1] == 0
        and abs(diverging[1]) == 1
    )
    short = main[0] if main else None
    long = diverging[0] if diverging else None
    track_delta = diverging[1] if diverging else None
    dv = model_path.replace("\\", "/")
    if dv.endswith("_mn.mdl"):
        dv = dv[: -len("_mn.mdl")] + "_dv.mdl"
    mn = dv[: -len("_dv.mdl")] + "_mn.mdl"
    record = {
        "kind": "switch",
        "Direction": direction,
        "StartDirection": direction,
        "EndDirection": direction,
        "hand": hand,
        "radius": radius,
        "short": short,
        "long": long,
        "track_delta": track_delta,
        "exact": exact,
        "condensed": exact and long > short,
        "dv": dv,
        "mn": mn,
        "model": dv,
    }
    if exact:
        record["MainMove"] = track.move_in_trackspace(short, direction, 0)
        record["DivMove"] = track.move_in_trackspace(long, direction, track_delta)
        record["Move"] = record["MainMove"]
    return record


def _parsed_catalog():

    global _PARSED
    if _PARSED is None:
        _PARSED = [geometry_from_model(model) for model in catalog_models()]
    return _PARSED


def register_switch_library(library=None):

    """Make every catalog model resolvable as a three-ended switch."""

    target = track.track_model_library if library is None else library
    for record in _parsed_catalog():
        target[record["dv"]] = record
        target[record["mn"]] = record
    return target


def select_switch(direction, hand):

    """Smallest condensed siding of this direction and hand.

    Hand is the side the diverging leg leaves toward ('left' or 'right'),
    decided by the track-count change, not by whichever file happens to
    be first in the catalog.
    """

    matches = [
        record
        for record in _parsed_catalog()
        if record["condensed"]
        and record["Direction"] == direction
        and record["hand"] == hand
        and record["track_delta"] == (-1 if hand == "left" else 1)
    ]
    if not matches:
        raise SwitchGeometryError(
            f"no condensed parallel siding for {direction} {hand} lands on the parallel grid"
        )
    matches.sort(key=lambda record: (record["long"], record["radius"], record["dv"]))
    return matches[0]


def _opposite(hand):

    return "right" if hand == "left" else "left"


def _phases(before, after):

    """Merges first, then splits. Each phase is non-overlapping.

    3L0R -> 0L3R is a left merge followed by a right split. Both sides
    growing or shrinking together stay one phase so the ladders can share
    a root. The order is a list so it can be swapped later.
    """

    before_left, before_right = before
    after_left, after_right = after
    phases = []
    mid_left, mid_right = before_left, before_right
    if after_left < mid_left or after_right < mid_right:
        merged = (min(after_left, mid_left), min(after_right, mid_right))
        phases.append(((mid_left, mid_right), merged, True))
        mid_left, mid_right = merged
    if after_left > mid_left or after_right > mid_right:
        phases.append(((mid_left, mid_right), (after_left, after_right), False))
    return phases


def _increase_layout(before, after, direction):

    """One forward ladder, station 0 at the switch points.

    `before` is the smaller count. Both deltas are zero or positive.
    """

    sample = None
    for hand in ("left", "right"):
        try:
            sample = select_switch(direction, hand)
            break
        except SwitchGeometryError:
            continue
    if sample is None:
        raise SwitchGeometryError(
            f"no condensed parallel siding for {direction} lands on the parallel grid"
        )
    short = sample["short"]
    long = sample["long"]
    add_left = after[0] - before[0]
    add_right = after[1] - before[1]
    if add_left < 0 or add_right < 0:
        raise ValueError(f"increase layout got a decrease: {before} -> {after}")

    shared_root = before == (0, 0) and add_left > 0 and add_right > 0
    if add_left >= add_right:
        first, second = "left", "right"
        first_count, second_count = add_left, add_right
    else:
        first, second = "right", "left"
        first_count, second_count = add_right, add_left
    shift_second = shared_root and second_count > 0
    if first_count == 0:
        total = 0
    elif shift_second and first_count == second_count:
        # Both sides leave the same point. The second ladder starts at the
        # end of the first switch's main leg, so the zone grows by `short`.
        total = first_count * long + short
    else:
        total = first_count * long

    switches = []

    def add_side(side, count, shift):
        if count <= 0:
            return
        sign = -1 if side == "left" else 1
        root = -before[0] if side == "left" else before[1]
        for index in range(count):
            origin_s = (short if shift else 0) + index * long
            switches.append(
                {
                    "side": side,
                    "track": root + sign * index,
                    "origin_s": origin_s,
                    "main_s": origin_s + short,
                    "div_track": root + sign * (index + 1),
                    "div_s": origin_s + long,
                }
            )

    add_side(first, first_count, False)
    add_side(second, second_count, shift_second)
    return {
        "before": before,
        "after": after,
        "short": short,
        "long": long,
        "total": total,
        "switches": switches,
    }


def grid_quantum(direction):

    """Smallest forward step that keeps both components on the 16-unit grid.

    A 1-in-4 slope moves 4 units sideways per 16 forward, so the props only
    land on the grid every 64. A 1-in-2 slope lands every 32.
    """

    if direction in ("1lt", "1rt"):
        return 64
    if direction in ("2lt", "2rt"):
        return 32
    return 16


def zone_length(before, after, direction):

    if tuple(before) == tuple(after):
        return 0
    total = 0
    for phase_before, phase_after, reverse in _phases(before, after):
        small, large = (phase_after, phase_before) if reverse else (phase_before, phase_after)
        total += _increase_layout(small, large, direction)["total"]
    return total


def _travel(station, total, reverse):

    return total - station if reverse else station


def _indices(mode):

    return range(-int(mode[0]), int(mode[1]) + 1)


def _station(origin, direction, heading, station, track_index):

    return track.updated_position(
        origin,
        track.move_in_trackspace(station, direction, track_index),
        heading,
    )


def place_transition(origin, direction, heading, before, after):

    """Write the ladders from `before` to `after` and return the end node position."""

    if tuple(before) == tuple(after):
        return origin
    register_switch_library()
    cursor = origin
    for phase_before, phase_after, reverse in _phases(before, after):
        small, large = (phase_after, phase_before) if reverse else (phase_before, phase_after)
        layout = _increase_layout(small, large, direction)
        _place_layout(cursor, direction, heading, layout, reverse, phase_before, phase_after)
        cursor = _station(cursor, direction, heading, layout["total"], 0)
    return cursor


def _place_layout(origin, direction, heading, layout, reverse, incoming, outgoing):

    total = layout["total"]
    points = {}
    occupied = {}

    def mark(track_index, station):
        points.setdefault(track_index, set()).add(int(station))

    for switch in layout["switches"]:
        hand = _opposite(switch["side"]) if reverse else switch["side"]
        spec = select_switch(direction, hand)
        origin_s = _travel(switch["origin_s"], total, reverse)
        main_s = _travel(switch["main_s"], total, reverse)
        div_s = _travel(switch["div_s"], total, reverse)
        yaw = heading + 180 if reverse else heading
        position = _station(origin, direction, heading, origin_s, switch["track"])
        vmfpy.add_entity(
            {
                "classname": "tp3_switch",
                "pos": position,
                "ang": (0, yaw, 0),
                "mdl": spec["mn"],
                "model_div": spec["dv"],
                "visgroup": "23",
            }
        )
        mark(switch["track"], origin_s)
        mark(switch["track"], main_s)
        mark(switch["div_track"], div_s)
        lo, hi = sorted((int(origin_s), int(main_s)))
        occupied.setdefault(switch["track"], []).append((lo, hi))

    for track_index in _indices(incoming):
        mark(track_index, 0)
    for track_index in _indices(outgoing):
        mark(track_index, total)

    for track_index, stations in points.items():
        ordered = sorted(stations)
        blocked = occupied.get(track_index, [])
        for start, end in zip(ordered, ordered[1:]):
            if any(lo == start and hi == end for lo, hi in blocked):
                continue
            gap = end - start
            if gap < 0:
                raise ValueError(
                    f"negative switch fill {gap} on track {track_index}"
                )
            if gap == 0:
                continue
            track.create_straight(
                _station(origin, direction, heading, start, track_index),
                gap,
                direction,
                heading,
            )


def describe_selection():

    """One chosen model per direction and hand, for the report."""

    rows = []
    seen = set()
    for record in _parsed_catalog():
        key = (record["Direction"], record["hand"])
        if key in seen or not record["condensed"]:
            continue
        try:
            chosen = select_switch(*key)
        except SwitchGeometryError:
            continue
        if (chosen["Direction"], chosen["hand"]) in seen:
            continue
        seen.add((chosen["Direction"], chosen["hand"]))
        rows.append(chosen)
    return rows
