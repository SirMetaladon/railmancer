"""Automatic build sheds.

One shed per ``buildN`` teleport Isaiah aimed at the spawn room. The shell
is a sector-sized skybox room. A flat TrakPak3 straight sits on the grass,
and a copy of the spawn door warps back to ``spawn``.
"""

import math
import re

from railmancer import cfg, sectors, tools, vmfparse, vmfpy
from railmancer.consolidate_straights import _pack_same_grade
from railmancer.straight_catalog import get_catalog

# Map brush limit is ±16384. Sector tops already stop at 16320.
MAP_LIMIT = 16384
MAP_Z_MIN = -16384
MAP_Z_MAX = 16320

WALL = 16
SUBFLOOR = 16
GRASS = 16
# Prototype rail origin is 24 above the grass slab (-16028 over -16052).
TRACK_ABOVE_GRASS = 24
STACK_GAP = 64
TRACK_YAW = -90

DOOR_W = 56
DOOR_PANEL_D = 2
DOOR_FRAME_D = 4
DOOR_PANEL_H = 108
DOOR_BAR_H = 4
DOOR_H = DOOR_PANEL_H + DOOR_BAR_H
JAMB_W = 4
TRIGGER_D = 8
DEST_CLEAR = 64
DOOR_TRACK_CLEAR = 64

NODRAW = "TOOLS/TOOLSNODRAW"
SKY = "TOOLS/TOOLSSKYBOX"
GRASS_TEX = "RAVINE/BLENDDIRTTOGRASS001"
DOOR_TEX = "METAL/OFFICEDOOR002"
FRAME_TEX = "CONCRETE/COMPUTERWALL007"

_BUILD = re.compile(r"^build(\d+)$", re.IGNORECASE)
_CLASS = re.compile(r'"classname"\s+"([^"]*)"')
_TARGET = re.compile(r'"target"\s+"([^"]*)"')
_ORIGIN = re.compile(r'"origin"\s+"([^"]*)"')
_TRIPLE = re.compile(
    r"(?:\(|\"v\"\s+\")"
    r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"
)
_FACE_KEYS = ("top", "bottom", "nx", "px", "py", "ny")


def _snap_up(value, grid=16):
    return int(math.ceil(value / grid) * grid)


def _snap_down(value, grid=16):
    return int(math.floor(value / grid) * grid)


def _snap_nearest(value, grid=16):
    return int(round(value / grid) * grid)


def _hits(a0, a1, b0, b1):
    return a0 < b1 and b0 < a1


def normalize_targets(explicit):

    # An int is build1..buildN. A list keeps the build<N> names, sorted.
    if isinstance(explicit, int):
        if explicit < 1:
            return []
        return [f"build{number}" for number in range(1, explicit + 1)]

    found = {}
    for item in explicit:
        match = _BUILD.match(str(item).strip())
        if not match:
            continue
        number = int(match.group(1))
        found[number] = f"build{number}"
    return [found[number] for number in sorted(found)]


def targets_in_vmf(text):

    if not text:
        return []
    found = {}
    for block in vmfparse.parse_blocks(text):
        if block.name != "entity" or block.close_brace < 0:
            continue
        body = text[block.start : block.close_brace + 1]
        kind = _CLASS.search(body)
        target = _TARGET.search(body)
        if not kind or kind.group(1).lower() != "trigger_teleport" or not target:
            continue
        match = _BUILD.match(target.group(1).strip())
        if not match:
            continue
        number = int(match.group(1))
        found[number] = f"build{number}"
    return [found[number] for number in sorted(found)]


def build_targets(text="", explicit=None):

    if explicit is not None:
        return normalize_targets(explicit)
    return targets_in_vmf(text)


def _aabb(text):

    points = _TRIPLE.findall(text)
    if not points:
        return None
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    zs = [float(point[2]) for point in points]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _union(first, second):

    return (
        min(first[0], second[0]),
        max(first[1], second[1]),
        min(first[2], second[2]),
        max(first[3], second[3]),
        min(first[4], second[4]),
        max(first[5], second[5]),
    )


def _snap_out(box):

    return (
        _snap_down(box[0]),
        _snap_up(box[1]),
        _snap_down(box[2]),
        _snap_up(box[3]),
        _snap_down(box[4]),
        _snap_up(box[5]),
    )


def _box_hits(first, second):

    return (
        _hits(first[0], first[1], second[0], second[1])
        and _hits(first[2], first[3], second[2], second[3])
        and _hits(first[4], first[5], second[4], second[5])
    )


def spawn_box_from_text(text, sector_size):

    """Room box around the player start and the build* triggers.

    World and entity solids that touch that seed, and are no bigger than
    one sector, are pulled in. That is the spawn shell. Anything wider
    (a ground hint, a whole sector) is left out.
    """

    if not text:
        return None
    blocks = vmfparse.parse_blocks(text)
    seeds = []
    for block in blocks:
        if block.name != "entity" or block.close_brace < 0:
            continue
        body = text[block.start : block.close_brace + 1]
        kind = _CLASS.search(body)
        if not kind:
            continue
        if kind.group(1) == "info_player_start":
            origin = _ORIGIN.search(body)
            if not origin:
                continue
            x, y, z = (float(value) for value in origin.group(1).split())
            seeds.append((x - 16, x + 16, y - 16, y + 16, z - 16, z + 16))
        elif kind.group(1).lower() == "trigger_teleport":
            target = _TARGET.search(body)
            if target and _BUILD.match(target.group(1).strip()):
                box = _aabb(body)
                if box:
                    seeds.append(box)
    if not seeds:
        return None

    box = seeds[0]
    for seed in seeds[1:]:
        box = _union(box, seed)

    pending = []
    for index, block in enumerate(blocks):
        if block.name != "solid" or block.close_brace < 0:
            continue
        body = text[block.start : block.close_brace + 1]
        solid = _aabb(body)
        if not solid:
            continue
        if (solid[1] - solid[0]) > sector_size or (solid[3] - solid[2]) > sector_size:
            continue
        pending.append(solid)

    changed = True
    while changed and pending:
        changed = False
        still = []
        for solid in pending:
            if _box_hits(solid, box):
                box = _union(box, solid)
                changed = True
            else:
                still.append(solid)
        pending = still
    return _snap_out(box)


def _column_indexes(sectors_per_map):

    # Same window sectors.sort_points_to_sector_grid_buckets keeps.
    limit = int(sectors_per_map)
    half = sectors_per_map / 2
    return [
        index
        for index in range(-limit - 1, limit + 2)
        if abs(index + 0.5) <= half
    ]


def _merge(intervals):

    ordered = sorted(intervals)
    if not ordered:
        return []
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _free_bands(blocked, buffer):

    expanded = _merge((start - buffer, end + buffer) for start, end in blocked)
    bands = []
    cursor = MAP_Z_MIN
    for start, end in expanded:
        if start > cursor:
            bands.append((cursor, min(start, MAP_Z_MAX)))
        cursor = max(cursor, end)
        if cursor >= MAP_Z_MAX:
            return bands
    if cursor < MAP_Z_MAX:
        bands.append((cursor, MAP_Z_MAX))
    return bands


def _blocked_in_column(sx, sy, sector_size, spawn_box):

    blocked = []
    for sector_id in sectors.sector_lookup_grid.get(f"{sx}x{sy}", ()):
        sector = sectors.Sectors.get(sector_id)
        if not sector:
            continue
        z0 = int(sector["floor"]) * 16
        z1 = int(sector["ceiling"]) * 16
        if z1 < z0:
            z0, z1 = z1, z0
        blocked.append((z0, z1))

    if spawn_box is None:
        return blocked
    x0 = sx * sector_size
    y0 = sy * sector_size
    if _hits(x0, x0 + sector_size, spawn_box[0], spawn_box[1]) and _hits(
        y0, y0 + sector_size, spawn_box[2], spawn_box[3]
    ):
        blocked.append((spawn_box[4], spawn_box[5]))
    return blocked


def find_slots(
    count,
    sector_size,
    shed_height,
    spawn_box=None,
    buffer=STACK_GAP,
    sectors_per_map=None,
):

    """Column origins ``(x0, y0, z0)`` for ``count`` sheds.

    Empty columns stack from the bottom. A sector, and the spawn room,
    keep a ``buffer`` of air. Everything stays on the 16-unit grid and
    inside the map.
    """

    if count < 1 or sector_size < 16 or shed_height < 16:
        return []
    if sectors_per_map is None:
        sectors_per_map = int(32768 / sector_size)
    slots = []
    for sx in _column_indexes(sectors_per_map):
        for sy in _column_indexes(sectors_per_map):
            x0 = sx * sector_size
            y0 = sy * sector_size
            x1 = x0 + sector_size
            y1 = y0 + sector_size
            if x0 < -MAP_LIMIT or y0 < -MAP_LIMIT or x1 > MAP_LIMIT or y1 > MAP_LIMIT:
                continue
            blocked = _blocked_in_column(sx, sy, sector_size, spawn_box)
            for band_start, band_end in _free_bands(blocked, buffer):
                z = _snap_up(band_start)
                limit = _snap_down(band_end)
                while z + shed_height <= limit and z >= MAP_Z_MIN:
                    slots.append((x0, y0, z))
                    if len(slots) >= count:
                        return slots
                    z += shed_height + buffer
    return slots


def fit_straights(sector_size, margin, catalog=None):

    """Largest flat 0fw pieces that fit inside the walls plus ``margin``."""

    catalog = catalog or get_catalog()
    interior = int(sector_size) - 2 * WALL
    usable = interior - 2 * max(0, int(margin))
    usable -= usable % 16
    if usable < 32:
        return []
    packed = _pack_same_grade(usable, "0fw", "0pg", catalog)
    if packed:
        return list(packed)
    remaining = usable
    picked = []
    for size in catalog.lengths_for("0fw", "0pg"):
        piece = catalog.get("0fw", "0pg", size)
        if piece is None:
            continue
        while remaining >= size:
            picked.append(piece)
            remaining -= size
    return picked


def _nodraw_faces():

    return {key: NODRAW for key in _FACE_KEYS}


def _shell(x0, y0, z0, size, height, visgroup):

    x1 = x0 + size
    y1 = y0 + size
    z1 = z0 + height
    z_floor = z0 + SUBFLOOR + GRASS
    vmfpy.add_faced_brush(
        x0, x1, y0, y1, z0, z0 + SUBFLOOR, _nodraw_faces(), visgroup
    )
    grass = _nodraw_faces()
    grass["top"] = GRASS_TEX
    vmfpy.add_faced_brush(
        x0 + WALL,
        x1 - WALL,
        y0 + WALL,
        y1 - WALL,
        z0 + SUBFLOOR,
        z_floor,
        grass,
        visgroup,
    )
    south = _nodraw_faces()
    south["py"] = SKY
    vmfpy.add_faced_brush(
        x0, x1, y0, y0 + WALL, z0 + SUBFLOOR, z1 - WALL, south, visgroup
    )
    north = _nodraw_faces()
    north["ny"] = SKY
    vmfpy.add_faced_brush(
        x0, x1, y1 - WALL, y1, z0 + SUBFLOOR, z1 - WALL, north, visgroup
    )
    west = _nodraw_faces()
    west["px"] = SKY
    vmfpy.add_faced_brush(
        x0, x0 + WALL, y0, y1, z0 + SUBFLOOR, z1 - WALL, west, visgroup
    )
    east = _nodraw_faces()
    east["nx"] = SKY
    vmfpy.add_faced_brush(
        x1 - WALL, x1, y0, y1, z0 + SUBFLOOR, z1 - WALL, east, visgroup
    )
    ceiling = _nodraw_faces()
    ceiling["bottom"] = SKY
    vmfpy.add_faced_brush(
        x0, x1, y0, y1, z1 - WALL, z1, ceiling, visgroup
    )


def _track_props(x0, y0, z0, sector_size, margin, pieces):

    if not pieces:
        return []
    length = sum(piece.length for piece in pieces)
    interior = sector_size - 2 * WALL
    y = y0 + WALL + (interior - length) // 2
    x = _snap_nearest(x0 + sector_size / 2)
    z = z0 + SUBFLOOR + GRASS + TRACK_ABOVE_GRASS
    placed = []
    pos = [x, y, z]
    for piece in pieces:
        placed.append((tuple(pos), piece))
        step = tools.rot_orth(piece.move, TRACK_YAW)
        pos = [int(pos[index] + int(step[index])) for index in range(3)]
    return placed


def _door(x0, y0, z0, size, x_track, return_target, name, visgroup):

    # South interior wall. The panel is shifted off the rail so the
    # arrival is not standing on it. Front face looks +Y, into the shed.
    z_floor = z0 + SUBFLOOR + GRASS
    y_back = y0 + WALL
    inner0 = x0 + WALL
    inner1 = x0 + size - WALL
    assembly = DOOR_W + 2 * JAMB_W
    origin = x_track + DOOR_TRACK_CLEAR - JAMB_W
    if origin + assembly > inner1:
        origin = inner1 - assembly
    if origin < inner0:
        origin = inner0
    panel0 = origin + JAMB_W
    panel1 = panel0 + DOOR_W

    def faces(front):
        painted = {key: FRAME_TEX for key in _FACE_KEYS}
        painted["ny"] = NODRAW
        painted["py"] = front
        return painted

    vmfpy.add_faced_brush(
        panel0,
        panel1,
        y_back,
        y_back + DOOR_PANEL_D,
        z_floor,
        z_floor + DOOR_PANEL_H,
        faces(DOOR_TEX),
        visgroup,
    )
    vmfpy.add_faced_brush(
        panel0,
        panel1,
        y_back,
        y_back + DOOR_FRAME_D,
        z_floor + DOOR_PANEL_H,
        z_floor + DOOR_H,
        faces(FRAME_TEX),
        visgroup,
    )
    for jamb in (origin, panel1):
        vmfpy.add_faced_brush(
            jamb,
            jamb + JAMB_W,
            y_back,
            y_back + DOOR_PANEL_D,
            z_floor,
            z_floor + DOOR_PANEL_H,
            faces(FRAME_TEX),
            visgroup,
        )

    y_trigger = y_back + DOOR_FRAME_D
    vmfpy.add_trigger_teleport(
        panel0,
        panel1,
        y_trigger,
        y_trigger + TRIGGER_D,
        z_floor,
        z_floor + DOOR_H,
        return_target,
        visgroup=visgroup,
        spawnflags="1",
        start_disabled="0",
    )
    dest_y = y_trigger + TRIGGER_D + DEST_CLEAR
    far = y0 + size - WALL - 16
    if dest_y > far:
        dest_y = max(y_trigger + TRIGGER_D + 16, far)
    vmfpy.add_entity(
        {
            "classname": "info_teleport_destination",
            "targetname": name,
            "pos": (panel0 + DOOR_W // 2, dest_y, z_floor + 16),
            "ang": (0, 90, 0),
            "visgroup": visgroup,
        }
    )


def add_shed(
    name,
    origin,
    sector_size,
    height,
    margin,
    return_target,
    visgroup=None,
):

    visgroup = visgroup or vmfpy.VISGROUP_BUILD_SHEDS
    x0, y0, z0 = (int(value) for value in origin)
    _shell(x0, y0, z0, sector_size, height, visgroup)
    pieces = fit_straights(sector_size, margin)
    x_track = _snap_nearest(x0 + sector_size / 2)
    for pos, piece in _track_props(x0, y0, z0, sector_size, margin, pieces):
        vmfpy.add_entity(
            {
                "classname": "prop_static",
                "pos": pos,
                "mdl": piece.model,
                "ang": (0, TRACK_YAW, 0),
                "skin": 0,
                "visgroup": visgroup,
            }
        )
    _door(x0, y0, z0, sector_size, x_track, return_target, name, visgroup)


def shed_member_spans(text):

    """World solids and entities already in the Build Sheds visgroup.

    The id comes from the name in this file's visgroups block.
    """

    ids = vmfparse.visgroup_ids_named(text, vmfpy.BUILD_SHEDS_VISGROUP_NAME)
    if not text or not ids:
        return []
    blocks = vmfparse.parse_blocks(text)
    entity_indexes = {
        index for index, block in enumerate(blocks) if block.name == "entity"
    }
    spans = []
    for index, block in enumerate(blocks):
        if block.close_brace < 0 or block.name not in ("entity", "solid"):
            continue
        if block.name == "solid" and vmfparse.has_ancestor(
            blocks, index, entity_indexes
        ):
            continue
        body = text[block.start : block.close_brace + 1]
        if not (vmfparse.block_visgroup_ids(body) & ids):
            continue
        spans.append((vmfparse.line_start(text, block.start), block.close_brace + 1))
    return spans


def apply(explicit=None):

    if explicit is None and not cfg.get("build_sheds_enabled"):
        return 0
    text = ""
    if vmfpy.base_map is not None and vmfpy.base_map.text:
        text = vmfpy.base_map.text
    targets = build_targets(text, explicit)
    if not targets:
        return 0

    size = int(cfg.get("sector_real_size"))
    height = int(cfg.get("build_shed_height"))
    margin = int(cfg.get("build_shed_track_margin"))
    return_target = cfg.get("build_shed_return_target")
    spawn = spawn_box_from_text(text, size) if text else None
    slots = find_slots(
        len(targets),
        size,
        height,
        spawn_box=spawn,
        sectors_per_map=int(cfg.get("sectors_per_map")),
    )
    if not slots:
        print(f"Build sheds: no open column for {len(targets)} shed(s).")
        return 0
    if len(slots) < len(targets):
        print(f"Build sheds: room for {len(slots)} of {len(targets)}.")
    if text and vmfpy.base_map is not None:
        vmfpy.base_map.consumed_spans.extend(shed_member_spans(text))
    for name, origin in zip(targets, slots):
        add_shed(name, origin, size, height, margin, return_target)
    return min(len(targets), len(slots))


def main(argv=None):

    # Inspect the sheds on their own. The map run uses the fitted sectors;
    # this writes an empty-grid preview (spawn is still avoided if --vmf).
    import argparse
    import sys
    from contextlib import redirect_stdout
    from io import StringIO

    parser = argparse.ArgumentParser(description="Write build sheds as VMF text.")
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--targets", default="")
    parser.add_argument("--vmf", default="")
    parser.add_argument("--size", type=int, default=3264)
    parser.add_argument("--height", type=int, default=1856)
    parser.add_argument("--margin", type=int, default=80)
    parser.add_argument("--return-target", default="spawn")
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)

    explicit = None
    text = ""
    if args.targets.strip():
        explicit = [part.strip() for part in args.targets.split(",") if part.strip()]
    elif args.count:
        explicit = args.count
    elif args.vmf:
        with open(args.vmf, encoding="utf-8") as handle:
            text = handle.read()
    else:
        explicit = 1

    targets = build_targets(text, explicit)
    size = max(int(args.size) // 16 * 16, 16)
    height = max(int(args.height) // 16 * 16, 160)
    vmfpy.Brushes.clear()
    vmfpy.Brush_Group_Keys.clear()
    vmfpy.Entities.clear()
    vmfpy.Brush_Entites.clear()
    vmfpy.Sector_Group_IDs.clear()
    vmfpy.clear_base_map()
    sectors.Sectors.clear()
    sectors.sector_lookup_grid.clear()
    spawn = spawn_box_from_text(text, size) if text else None
    slots = find_slots(
        len(targets),
        size,
        height,
        spawn_box=spawn,
        sectors_per_map=int(32768 / size),
    )
    for name, origin in zip(targets, slots):
        add_shed(name, origin, size, height, args.margin, args.return_target)
    with redirect_stdout(StringIO()):
        content = vmfpy.assemble_vmf()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(content)
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    main()
