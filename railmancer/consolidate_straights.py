"""Consolidate adjacent TrakPak3 straight props into longer stock pieces.

Pipeline hook (before the final VMF write):

    from railmancer import consolidate_straights
    consolidate_straights.consolidate_inplace(smooth_grade=False)

External VMF copy:

    python3 tools/consolidate_vmf_straights.py input.vmf
    python3 tools/consolidate_vmf_straights.py input.vmf --smooth-grade -o out.vmf

Rules:
- Only ``/straights/`` props are rewritten. Arcs, switches, markers stay put.
- Without ``smooth_grade``, flat (``0pg``) runs and each graded token run merge
  separately. Adjacent different grades are not mixed.
- With ``smooth_grade``, collinear straights of the same direction are
  recomposed so total length and total rise match, using any grade versions
  available for that direction (including flat fillers).
- Chain endpoints keep the same world positions (verified with joincheck).
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import sys
import types
from dataclasses import dataclass

sys.modules.setdefault("turtle", types.ModuleType("turtle"))

from railmancer import joincheck, tools, track, vmfpy
from railmancer.joincheck import _prop_from_entity_block
from railmancer.straight_catalog import (
    StraightCatalog,
    StraightPiece,
    get_catalog,
    is_straight_model,
    parse_straight_name,
)


@dataclass
class ConsolidateStats:
    straight_before: int = 0
    straight_after: int = 0
    runs_merged: int = 0
    pieces_removed: int = 0
    smooth_grade: bool = False

    @property
    def saved(self) -> int:
        return self.straight_before - self.straight_after


@dataclass
class _StraightRef:
    index: int
    prop: dict
    model: str
    direction: str
    grade_token: str
    length: int
    rise: int
    yaw: float
    end_a: tuple
    end_b: tuple


def _yaw_of(prop) -> float:
    ang = prop["ang"]
    if isinstance(ang, (int, float)):
        return float(ang)
    return float(ang[1])


def _is_track_prop(prop) -> bool:
    model = str(prop.get("mdl", "")).replace("\\", "/").lower()
    if "trakpak" not in model:
        return False
    return (
        "/straights/" in model
        or "/arcs/" in model
        or "/banked/" in model
        or "/switches/sidings/" in model
    )


def _library_for(props):
    track_props = [prop for prop in props if _is_track_prop(prop)]
    library, unknown = joincheck.library_from_prop_names(track_props)
    if unknown:
        raise ValueError(
            "could not parse geometry for: " + ", ".join(sorted(set(unknown)))
        )
    return library


def _straight_refs(props, library, catalog: StraightCatalog) -> list[_StraightRef]:
    refs = []
    for index, prop in enumerate(props):
        model = prop["mdl"].replace("\\", "/")
        if not is_straight_model(model):
            continue
        parsed = parse_straight_name(model)
        if parsed is None:
            continue
        piece = catalog.get(
            parsed["direction"], parsed["grade_token"], parsed["length"]
        )
        rise = (
            piece.rise
            if piece is not None
            else abs(int(library[model]["Move"][2]))
        )
        yaw = _yaw_of(prop)
        end_a, end_b = joincheck.prop_endpoints(model, prop["pos"], yaw, library)
        refs.append(
            _StraightRef(
                index=index,
                prop=prop,
                model=model,
                direction=parsed["direction"],
                grade_token=parsed["grade_token"],
                length=parsed["length"],
                rise=rise,
                yaw=yaw,
                end_a=end_a,
                end_b=end_b,
            )
        )
    return refs


def _endpoint_owners(refs: list[_StraightRef]):
    owners = {}
    for ref_i, ref in enumerate(refs):
        for which, key in enumerate((ref.end_a, ref.end_b)):
            owners.setdefault(key, []).append((ref_i, which))
    return owners


def _other_end(ref: _StraightRef, key):
    if ref.end_a == key:
        return ref.end_b
    if ref.end_b == key:
        return ref.end_a
    raise ValueError("endpoint not on ref")


def _compatible(a: _StraightRef, b: _StraightRef, smooth_grade: bool) -> bool:
    if a.direction != b.direction:
        return False
    if not smooth_grade and a.grade_token != b.grade_token:
        return False
    return True


def _build_paths(refs: list[_StraightRef], smooth_grade: bool) -> list[list[int]]:
    """Return paths as lists of ref indices (degree <= 2 chains)."""

    owners = _endpoint_owners(refs)
    neighbors = {i: [] for i in range(len(refs))}

    for key, hits in owners.items():
        if len(hits) != 2:
            continue
        (i, _), (j, _) = hits
        if i == j:
            continue
        if not _compatible(refs[i], refs[j], smooth_grade):
            continue
        neighbors[i].append((j, key))
        neighbors[j].append((i, key))

    for i, edges in list(neighbors.items()):
        uniq = {}
        for j, key in edges:
            uniq.setdefault(j, key)
        neighbors[i] = [(j, key) for j, key in uniq.items()]

    order = sorted(
        range(len(refs)),
        key=lambda i: (len(neighbors[i]) != 1, i),
    )
    visited = set()
    paths = []
    for start in order:
        if start in visited:
            continue
        component = _component(start, neighbors)
        visited.update(component)
        ends = [n for n in component if len(neighbors[n]) <= 1]
        if not ends:
            # Closed loop of straights — leave alone as singles.
            for node in component:
                paths.append([node])
            continue
        paths.append(_trace_path(ends[0], neighbors))
    return paths


def _component(start, neighbors):
    stack = [start]
    seen = {start}
    while stack:
        node = stack.pop()
        for other, _key in neighbors[node]:
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return seen


def _trace_path(start, neighbors):
    path = [start]
    if not neighbors[start]:
        return path
    prev = None
    current = start
    while True:
        options = [edge for edge in neighbors[current] if edge[0] != prev]
        if not options:
            break
        if len(options) > 1 and prev is not None:
            break
        nxt, _key = options[0]
        path.append(nxt)
        prev, current = current, nxt
        if current == start:
            break
    return path


def _path_geometry(path: list[int], refs: list[_StraightRef]):
    """Ordered endpoints along a merge path and total rise/length."""

    if len(path) == 1:
        ref = refs[path[0]]
        return {
            "start": ref.end_a,
            "end": ref.end_b,
            "length": ref.length,
            "rise": _directed_rise(ref, ref.end_a, ref.end_b),
        }

    a = refs[path[0]]
    b = refs[path[1]]
    shared = None
    for key in (a.end_a, a.end_b):
        if key in (b.end_a, b.end_b):
            shared = key
            break
    if shared is None:
        raise ValueError("path nodes are not connected")

    start = a.end_b if shared == a.end_a else a.end_a
    ordered = [start]
    rise = 0
    length = 0
    current_key = start
    for ref_i in path:
        ref = refs[ref_i]
        other = _other_end(ref, current_key)
        rise += _directed_rise(ref, current_key, other)
        length += ref.length
        ordered.append(other)
        current_key = other

    return {
        "start": ordered[0],
        "end": ordered[-1],
        "length": length,
        "rise": rise,
    }


def _directed_rise(ref: _StraightRef, from_key, to_key) -> int:
    return int(to_key[0][2] - from_key[0][2])


def _pack_same_grade(
    length: int, direction: str, grade_token: str, catalog: StraightCatalog
) -> list[StraightPiece] | None:
    available = catalog.lengths_for(direction, grade_token)
    if not available:
        return None
    remaining = length
    picked: list[StraightPiece] = []
    for size in available:
        piece = catalog.get(direction, grade_token, size)
        if piece is None:
            continue
        while remaining >= size:
            picked.append(piece)
            remaining -= size
    if remaining == 0:
        return picked
    return _pack_exact(length, direction, grade_token, catalog)


def _pack_exact(
    length: int, direction: str, grade_token: str, catalog: StraightCatalog
) -> list[StraightPiece] | None:
    available = list(catalog.lengths_for(direction, grade_token))
    if not available:
        return None
    if length == 0:
        return []
    parent = {length: None}
    queue = [length]
    while queue:
        left = queue.pop(0)
        if left == 0:
            break
        for size in available:
            if size > left:
                continue
            nxt = left - size
            if nxt in parent:
                continue
            parent[nxt] = (left, size)
            queue.append(nxt)
    if 0 not in parent:
        return None
    pieces = []
    cursor = 0
    while cursor != length:
        prev, size = parent[cursor]
        piece = catalog.get(direction, grade_token, size)
        if piece is None:
            return None
        pieces.append(piece)
        cursor = prev
    pieces.reverse()
    return pieces


def _pack_smooth(
    length: int, rise: int, direction: str, catalog: StraightCatalog
) -> list[tuple[StraightPiece, int]] | None:
    """Fewest pieces with exact length and signed rise."""

    if length < 0:
        return None
    if length == 0:
        return [] if rise == 0 else None

    options: list[tuple[StraightPiece, int]] = []
    for piece in catalog.by_direction.get(direction, ()):
        if piece.rise == 0:
            options.append((piece, 0))
        else:
            options.append((piece, piece.rise))
            options.append((piece, -piece.rise))

    uniq = {}
    for piece, signed in options:
        uniq.setdefault((piece.length, signed), (piece, signed))
    options = list(uniq.values())
    options.sort(key=lambda item: (-item[0].length, -abs(item[1])))

    max_abs = max(abs(rise), length // 32 + 4)
    dp = {0: {0: (0, None)}}
    for covered in range(0, length + 1):
        if covered not in dp:
            continue
        for cur_rise, (count, _prev) in list(dp[covered].items()):
            for piece, signed in options:
                nxt_len = covered + piece.length
                if nxt_len > length:
                    continue
                nxt_rise = cur_rise + signed
                if abs(nxt_rise) > max_abs and abs(rise) <= max_abs:
                    continue
                bucket = dp.setdefault(nxt_len, {})
                prev_best = bucket.get(nxt_rise)
                candidate = (count + 1, (covered, cur_rise, piece, signed))
                if prev_best is None or candidate[0] < prev_best[0]:
                    bucket[nxt_rise] = candidate

    if length not in dp or rise not in dp[length]:
        return None

    out: list[tuple[StraightPiece, int]] = []
    cursor_len = length
    cursor_rise = rise
    while cursor_len != 0 or cursor_rise != 0:
        _count, prev = dp[cursor_len][cursor_rise]
        if prev is None:
            break
        prev_len, prev_rise, piece, signed = prev
        out.append((piece, signed))
        cursor_len, cursor_rise = prev_len, prev_rise
    out.reverse()
    if sum(p.length for p, _ in out) != length:
        return None
    if sum(z for _, z in out) != rise:
        return None
    return out


def _choose_base_yaw(geom, refs, path) -> float:
    start_key = geom["start"]
    first = refs[path[0]]
    origin_key = joincheck.position_key(first.prop["pos"])
    if origin_key == start_key[0]:
        return first.yaw
    return first.yaw + 180.0


def _advance(pos, move, yaw):
    rotated = tools.rot_orth(move, yaw)
    return [float(pos[i]) + float(rotated[i]) for i in range(3)]


def _round_pos(pos):
    out = []
    for value in pos:
        rounded = round(float(value))
        out.append(int(rounded) if abs(float(value) - rounded) < 1e-6 else float(value))
    return out


def _template_ang(template_prop, yaw):
    ang = template_prop["ang"]
    if isinstance(ang, (int, float)):
        return (0.0, float(yaw), 0.0)
    return (float(ang[0]), float(yaw), float(ang[2]))


def _place_run(
    geom,
    packed: list[tuple[StraightPiece, int]],
    base_yaw: float,
    template_prop: dict,
) -> list[dict]:
    current = [float(v) for v in geom["start"][0]]
    entities = []

    for piece, signed_rise in packed:
        move = list(piece.move)
        if signed_rise < 0:
            travel = (move[0], move[1], -abs(move[2]))
            next_pos = _advance(current, travel, base_yaw)
            yaw = base_yaw + 180.0
            origin = next_pos
            check = _advance(origin, move, yaw)
            if joincheck.position_key(check) != joincheck.position_key(current):
                origin = current
                next_pos = _advance(origin, move, yaw)
            prop = copy.deepcopy(template_prop)
            prop["mdl"] = piece.model
            prop["pos"] = _round_pos(origin)
            prop["ang"] = _template_ang(template_prop, yaw)
            entities.append(prop)
            current = (
                next_pos
                if joincheck.position_key(origin) != joincheck.position_key(current)
                else _advance(origin, move, yaw)
            )
        else:
            yaw = base_yaw
            prop = copy.deepcopy(template_prop)
            prop["mdl"] = piece.model
            prop["pos"] = _round_pos(current)
            prop["ang"] = _template_ang(template_prop, yaw)
            entities.append(prop)
            current = _advance(current, move, yaw)

    if joincheck.position_key(current) != joincheck.position_key(geom["end"][0]):
        raise ValueError(
            f"consolidated run missed end: got {joincheck.position_key(current)} "
            f"want {joincheck.position_key(geom['end'][0])}"
        )
    return entities


def _pack_for_run(
    geom,
    direction: str,
    grade_token: str,
    smooth_grade: bool,
    catalog: StraightCatalog,
) -> list[tuple[StraightPiece, int]] | None:
    length = geom["length"]
    rise = geom["rise"]

    if smooth_grade:
        packed = _pack_smooth(length, rise, direction, catalog)
        if packed is not None:
            return packed

    pieces = _pack_same_grade(length, direction, grade_token, catalog)
    if pieces is None:
        return None

    sample = catalog.grade_info.get(direction, {}).get(grade_token)
    if sample is None:
        return None

    if grade_token == "0pg":
        if rise != 0:
            return None
        return [(piece, 0) for piece in pieces]

    total = sum(piece.rise for piece in pieces)
    if total != abs(rise):
        return None
    if rise == 0:
        return None
    sign = 1 if rise > 0 else -1
    return [(piece, sign * piece.rise) for piece in pieces]


def _replacement_preserves_ends(placed, geom, library) -> bool:
    trial = dict(library)
    for prop in placed:
        if prop["mdl"] not in trial:
            parsed = track.process_file(prop["mdl"])
            if not parsed:
                return False
            trial[prop["mdl"]] = parsed[0]
    counts, _ = joincheck.tally_endpoints(placed, trial)
    open_ends = {key for key, count in counts.items() if count == 1}
    return open_ends == {geom["start"], geom["end"]}


def consolidate_props(
    props: list,
    *,
    smooth_grade: bool = False,
    catalog: StraightCatalog | None = None,
) -> tuple[list, ConsolidateStats]:
    """Return a new prop list with straights consolidated."""

    catalog = catalog or get_catalog()
    library = _library_for(props)
    refs = _straight_refs(props, library, catalog)
    stats = ConsolidateStats(
        straight_before=len(refs),
        smooth_grade=smooth_grade,
    )
    if len(refs) < 2:
        stats.straight_after = len(refs)
        return copy.deepcopy(props), stats

    paths = _build_paths(refs, smooth_grade)
    replace_indices = set()
    new_straights: list[dict] = []

    for path in paths:
        if len(path) < 2:
            continue
        geom = _path_geometry(path, refs)
        direction = refs[path[0]].direction
        grade_token = refs[path[0]].grade_token
        packed = _pack_for_run(
            geom, direction, grade_token, smooth_grade, catalog
        )
        if packed is None or len(packed) >= len(path):
            continue
        try:
            base_yaw = _choose_base_yaw(geom, refs, path)
            placed = _place_run(geom, packed, base_yaw, refs[path[0]].prop)
        except ValueError:
            continue
        if not _replacement_preserves_ends(placed, geom, library):
            continue

        for ref_i in path:
            replace_indices.add(refs[ref_i].index)
        new_straights.extend(placed)
        stats.runs_merged += 1
        stats.pieces_removed += len(path) - len(placed)

    out = []
    for index, prop in enumerate(props):
        if index in replace_indices:
            continue
        out.append(copy.deepcopy(prop))
    out.extend(new_straights)
    stats.straight_after = stats.straight_before - stats.pieces_removed
    return out, stats


def consolidate(
    entities: list,
    *,
    smooth_grade: bool = False,
    catalog: StraightCatalog | None = None,
) -> list:
    """Consolidate straights in a ``vmfpy``-style entity list."""

    mdl_entities = [
        ent for ent in entities if isinstance(ent, dict) and "mdl" in ent
    ]
    others = [
        ent for ent in entities if not (isinstance(ent, dict) and "mdl" in ent)
    ]
    consolidated, _stats = consolidate_props(
        mdl_entities, smooth_grade=smooth_grade, catalog=catalog
    )
    return others + consolidated


def consolidate_inplace(*, smooth_grade: bool = False) -> ConsolidateStats:
    """Rewrite ``vmfpy.Entities`` straights in place. Call before ``write_to_vmf``."""

    entities = vmfpy.get_entities()
    mdl_entities = [
        ent for ent in entities if isinstance(ent, dict) and "mdl" in ent
    ]
    others = [
        ent for ent in entities if not (isinstance(ent, dict) and "mdl" in ent)
    ]
    consolidated, stats = consolidate_props(mdl_entities, smooth_grade=smooth_grade)
    entities[:] = others + consolidated
    return stats


def _entity_id(block: str) -> int | None:
    match = re.search(r'"id"\s+"(\d+)"', block)
    if not match:
        return None
    return int(match.group(1))


def _synthesize_prop_static(prop: dict, ent_id: int) -> str:
    ang = prop["ang"]
    if isinstance(ang, (int, float)):
        pitch, yaw, roll = 0.0, float(ang), 0.0
    else:
        pitch, yaw, roll = float(ang[0]), float(ang[1]), float(ang[2])
    pos = prop["pos"]
    vis = ""
    if prop.get("visgroup"):
        vis = f'\n\t\t"visgroupid" "{prop["visgroup"]}"'
    return (
        "entity\n"
        "{\n"
        f'\t"id" "{ent_id}"\n'
        '\t"classname" "prop_static"\n'
        f'\t"angles" "{pitch} {yaw} {roll}"\n'
        '\t"fademindist" "-1"\n'
        '\t"fadescale" "1"\n'
        f'\t"model" "{prop["mdl"]}"\n'
        f'\t"skin" "{prop.get("skin", 0)}"\n'
        '\t"solid" "6"\n'
        f'\t"origin" "{pos[0]} {pos[1]} {pos[2]}"\n'
        "\teditor\n"
        "\t{\n"
        '\t\t"color" "200 200 150"\n'
        '\t\t"visgroupshown" "1"\n'
        f'\t\t"visgroupautoshown" "1"{vis}\n'
        '\t\t"logicalpos" "[0 0]"\n'
        "\t}\n"
        "}\n"
    )


def _iter_full_entity_blocks(vmf_text: str):
    """Yield (start, end, brace_body) for each top-level-ish entity block."""

    search_from = 0
    while True:
        at = vmf_text.find("entity", search_from)
        if at < 0:
            break
        # Skip if "entity" is inside a quoted string by requiring a brace soon.
        brace = vmf_text.find("{", at)
        if brace < 0:
            break
        between = vmf_text[at + 6 : brace]
        if between.strip() not in ("",):
            search_from = at + 6
            continue
        depth = 0
        cursor = brace
        end = None
        while cursor < len(vmf_text):
            ch = vmf_text[cursor]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = cursor + 1
                    break
            cursor += 1
        if end is None:
            break
        yield at, end, vmf_text[brace:end]
        search_from = end


def consolidate_vmf_text(
    vmf_text: str,
    *,
    smooth_grade: bool = False,
    catalog: StraightCatalog | None = None,
) -> tuple[str, ConsolidateStats]:
    """Consolidate straights inside full VMF text; return new text + stats."""

    catalog = catalog or get_catalog()
    markers = joincheck.parse_vmf_markers(vmf_text)

    blocks = list(_iter_full_entity_blocks(vmf_text))
    track_props = []
    track_block_indices = []
    for index, (_start, _end, body) in enumerate(blocks):
        prop = _prop_from_entity_block(body)
        if prop is None:
            continue
        track_props.append(prop)
        track_block_indices.append(index)

    consolidated, stats = consolidate_props(
        track_props, smooth_grade=smooth_grade, catalog=catalog
    )
    new_straight_props = [p for p in consolidated if is_straight_model(p["mdl"])]

    original_straight_indices = {
        track_block_indices[local_i]
        for local_i, prop in enumerate(track_props)
        if is_straight_model(prop["mdl"])
    }

    max_id = 0
    for _start, _end, body in blocks:
        ent_id = _entity_id(body)
        if ent_id is not None:
            max_id = max(max_id, ent_id)

    pieces = []
    cursor = 0
    for index, (start, end, _body) in enumerate(blocks):
        pieces.append(vmf_text[cursor:start])
        if index in original_straight_indices:
            cursor = end
            if cursor < len(vmf_text) and vmf_text[cursor] == "\n":
                cursor += 1
            continue
        pieces.append(vmf_text[start:end])
        cursor = end
    pieces.append(vmf_text[cursor:])
    body = "".join(pieces)

    injection_parts = []
    for prop in new_straight_props:
        max_id += 1
        injection_parts.append(_synthesize_prop_static(prop, max_id))
    injection = "".join(injection_parts)

    insert_at = body.rfind("\ncameras")
    if insert_at < 0:
        insert_at = len(body)
    out_text = (
        body[:insert_at]
        + ("\n" if insert_at > 0 and injection else "")
        + injection
        + body[insert_at:]
    )

    verify_props = joincheck.parse_vmf_track_props(out_text)
    library, unknown = joincheck.library_from_prop_names(verify_props)
    if unknown:
        raise ValueError("post-consolidate unknown models: " + ", ".join(unknown))
    if markers:
        problems, _counts = joincheck.audit_marked_props(
            verify_props, library, markers
        )
    else:
        problems = joincheck.audit_props(verify_props, library)
    hard = [
        problem
        for problem in problems
        if "invalid junction" in problem or "missing" in problem
    ]
    if hard:
        raise ValueError("consolidation broke joints:\n  " + "\n  ".join(hard))

    return out_text, stats


def consolidate_vmf_file(
    input_path: str,
    output_path: str | None = None,
    *,
    smooth_grade: bool = False,
    catalog: StraightCatalog | None = None,
) -> ConsolidateStats:
    """Read a VMF, write a consolidated copy, return stats."""

    input_path = os.path.abspath(input_path)
    if output_path is None:
        root, ext = os.path.splitext(input_path)
        output_path = root + "_consolidated" + (ext or ".vmf")
    with open(input_path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        text = handle.read()
    new_text, stats = consolidate_vmf_text(
        text, smooth_grade=smooth_grade, catalog=catalog
    )
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(new_text)
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Consolidate fragmented TrakPak3 straight props in a VMF."
    )
    parser.add_argument("vmf", help="input VMF path")
    parser.add_argument(
        "-o",
        "--output",
        help="output VMF path (default: <input>_consolidated.vmf)",
    )
    parser.add_argument(
        "--smooth-grade",
        action="store_true",
        help="redistribute grade over collinear runs using mixed grade versions",
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="overwrite the input file instead of writing a copy",
    )
    args = parser.parse_args(argv)
    output = args.vmf if args.inplace else args.output
    stats = consolidate_vmf_file(args.vmf, output, smooth_grade=args.smooth_grade)
    dest = output or (os.path.splitext(args.vmf)[0] + "_consolidated.vmf")
    print(
        f"wrote {dest}: straights {stats.straight_before} -> {stats.straight_after} "
        f"(saved {stats.saved}, runs merged {stats.runs_merged}, "
        f"smooth_grade={stats.smooth_grade})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
