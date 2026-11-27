# info_null markers, milepost props, and warp primitives along a route.
# Switch ladders are not part of the distance, same as run_plain: a step
# with switch_zone has no model, so only placed pieces add length.
# Mileposts and warps are two-option pairs. collapse_quantum_switchstands
# keeps the side farther from the rails, the same pass the switch stands use.

import math

import numpy as np

from railmancer import cfg, tools, track, vmfpy


def plain_pieces(steps):

    # The model on a step is the piece that ends at that step. Its origin
    # is the previous node, which is where write_track plants the centerline.
    pieces = []
    station = 0.0
    prev = None
    for step in steps or []:
        model = step.get("model") or ""
        if prev is not None and model and not step.get("switch_zone"):
            length = float(track.get_length(model))
            node = prev["node"]
            pieces.append(
                {
                    "station": station,
                    "origin": node[0],
                    "direction": node[1],
                    "heading": node[2],
                    "length": length,
                    "model": model,
                }
            )
            station += length
        prev = step
    return pieces


def plain_length(pieces):

    if not pieces:
        return 0.0
    last = pieces[-1]
    return float(last["station"]) + float(last["length"])


def marker_name(mile, prefix="mp"):

    mile = round(float(mile), 4)
    text = f"{mile:.4f}".rstrip("0").rstrip(".")
    if "." not in text:
        text = text + ".0"
    whole, frac = text.split(".", 1)
    return prefix + "_" + whole + "_" + frac


def interval_distances(interval_miles, total):

    step = float(tools.inches(interval_miles))
    if step <= 0:
        return []
    distances = []
    n = 0
    while n * step <= float(total) + 1e-4:
        distances.append(n * step)
        n += 1
        if n > 100000:
            break
    return distances


def nearest_piece(pieces, distance):

    best = None
    best_delta = None
    for piece in pieces:
        delta = abs(float(piece["station"]) - float(distance))
        if best is None or delta < best_delta:
            best = piece
            best_delta = delta
    return best


def _whole(value):

    value = float(value)
    nearest = round(value)
    if abs(value - nearest) <= 1e-6:
        return int(nearest)
    return round(value, 4)


def _xyz(pos):

    return (_whole(pos[0]), _whole(pos[1]), _whole(pos[2]))


def track_yaw(direction, heading):

    return float(heading) + float(track.direction_to_angle(direction))


def yaw_toward(origin, pos):

    # Source yaw: 0 faces +X, 90 faces +Y. The vector is from the wayside
    # point back to the track centerline.
    dx = float(origin[0]) - float(pos[0])
    dy = float(origin[1]) - float(pos[1])
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(dy, dx))


def side_positions(origin, direction, heading, offset):

    # Same frame as add_switch_stand. At heading 0 the rail runs toward -X
    # and +Y is tracks_over_right. The first option is -Y, the second is +Y,
    # which is the order collapse_quantum_switchstands already compares.
    yaw = track_yaw(direction, heading)
    origin = np.asarray(origin, dtype=float)
    neg_y = np.add(origin, tools.rot3(np.array([0.0, -float(offset), 0.0]), yaw))
    pos_y = np.add(origin, tools.rot3(np.array([0.0, float(offset), 0.0]), yaw))
    return neg_y, pos_y, yaw


def _above(origin, z_offset):

    return (_whole(origin[0]), _whole(origin[1]), _whole(float(origin[2]) + float(z_offset)))


def _add_wayside(piece, offset, classname, targetname, toward_track):

    origin = piece["origin"]
    neg_y, pos_y, yaw = side_positions(
        origin, piece["direction"], piece["heading"], offset
    )
    if toward_track:
        yaw_neg = yaw_toward(origin, neg_y)
        yaw_pos = yaw_toward(origin, pos_y)
    else:
        # Along the rail, flipped on the +Y side, same as the stand model.
        yaw_neg = yaw
        yaw_pos = yaw + 180.0

    def one(pos, ang):
        item = {
            "classname": classname,
            "pos": _xyz(pos),
            "ang": (0, _whole(ang), 0),
            "visgroup": vmfpy.VISGROUP_MARKERS,
        }
        if targetname:
            item["targetname"] = targetname
        if classname == "prop_static":
            item["mdl"] = cfg.get("milepost_model")
        return item

    vmfpy.add_entity(
        [
            ["collapse", _xyz(neg_y), _xyz(pos_y)],
            one(neg_y, yaw_neg),
            one(pos_y, yaw_pos),
        ]
    )


def _place_markers(pieces, interval):

    if not pieces:
        return
    if interval is None:
        interval = cfg.get("marker_interval_miles")
    z_offset = cfg.get("marker_z_offset")
    start = cfg.get("start_milepost")
    total = plain_length(pieces)
    for distance in interval_distances(interval, total):
        piece = nearest_piece(pieces, distance)
        mile = start + tools.miles(distance)
        vmfpy.add_entity(
            {
                "classname": "info_null",
                "targetname": marker_name(mile),
                "pos": _above(piece["origin"], z_offset),
                "visgroup": vmfpy.VISGROUP_MARKERS,
            }
        )


def _place_mileposts(pieces, interval):

    if not pieces:
        return
    if interval is None:
        interval = cfg.get("milepost_interval_miles")
    offset = cfg.get("side_offset")
    start = cfg.get("start_milepost")
    total = plain_length(pieces)
    for distance in interval_distances(interval, total):
        piece = nearest_piece(pieces, distance)
        mile = start + tools.miles(distance)
        _add_wayside(piece, offset, "prop_static", marker_name(mile, "post"), False)


def _place_warps(pieces, warps):

    if not pieces or not warps:
        return
    offset = cfg.get("side_offset")
    start = cfg.get("start_milepost")
    total = plain_length(pieces)
    for warp in warps:
        mile = float(warp["mile"])
        distance = float(tools.inches(mile - start))
        if distance < -1e-4 or distance > total + 1e-4:
            continue
        piece = nearest_piece(pieces, max(distance, 0.0))
        _add_wayside(
            piece,
            offset,
            "info_teleport_destination",
            warp.get("name", marker_name(mile, "warp")),
            True,
        )


def place(steps, warps=None, marker_interval=None, milepost_interval=None):

    pieces = plain_pieces(steps)
    _place_markers(pieces, marker_interval)
    _place_mileposts(pieces, milepost_interval)
    _place_warps(pieces, warps)
