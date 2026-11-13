"""Precompiled catalog of TrakPak3 straight pieces.

Lengths match ``track.decompose_length_to_straights``. Grade tokens, real
percentages, grade levels, Z rise, and model paths are baked from the
committed manifest so consolidation does not need ``.mdl`` bytes.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from railmancer.trakpak_manifest import DEFAULT_MANIFEST, load_manifest

# Same set ``decompose_length_to_straights`` searches. Keep in sync.
ALLOWED_LENGTHS = (
    32,
    48,
    64,
    96,
    128,
    192,
    256,
    384,
    512,
    768,
    1024,
    1536,
    2048,
    3072,
    4096,
    6144,
    8192,
)

_STRAIGHT_NAME = re.compile(
    r"^s(?P<length>\d+)_"
    r"(?P<direction>\w+)_"
    r"(?P<grade>-?\d+pg)_"
    r"\+(?P<change_x>\d+)x"
    r"(?P<change_y>[+-]?\d+)x"
    r"(?P<change_z>[+-]?\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StraightPiece:
    """One stock straight model."""

    model: str
    direction: str
    grade_token: str
    real_grade: float
    grade_level: int
    length: int
    move: tuple[int, int, int]
    change_y: int
    rise: int  # Move[2]; always >= 0 in the pack (downhill = reversed prop)


@dataclass
class StraightCatalog:
    """Lookup tables for consolidation and packing."""

    pieces: tuple[StraightPiece, ...]
    # (direction, grade_token, length) -> piece
    by_key: dict[tuple[str, str, int], StraightPiece]
    # direction -> grade_token -> sorted lengths (desc)
    lengths_by_grade: dict[str, dict[str, tuple[int, ...]]]
    # direction -> grade_token -> StraightPiece sample (for metadata)
    grade_info: dict[str, dict[str, StraightPiece]]
    # direction -> all pieces (for grade smoothing)
    by_direction: dict[str, tuple[StraightPiece, ...]]

    def get(self, direction: str, grade_token: str, length: int) -> StraightPiece | None:
        return self.by_key.get((direction, grade_token, length))

    def lengths_for(self, direction: str, grade_token: str) -> tuple[int, ...]:
        return self.lengths_by_grade.get(direction, {}).get(grade_token, ())

    def grades_for(self, direction: str) -> tuple[str, ...]:
        return tuple(self.lengths_by_grade.get(direction, {}).keys())


_CATALOG: StraightCatalog | None = None


def parse_straight_name(model: str) -> dict | None:
    """Pull length / direction / grade token out of a straight model path."""

    name = model.replace("\\", "/").rsplit("/", 1)[-1]
    if name.lower().endswith(".mdl"):
        name = name[:-4]
    match = _STRAIGHT_NAME.match(name)
    if not match:
        return None
    return {
        "length": int(match.group("length")),
        "direction": match.group("direction"),
        "grade_token": match.group("grade"),
        "change_x": int(match.group("change_x")),
        "change_y": int(match.group("change_y")),
        "change_z": int(match.group("change_z")),
    }


def is_straight_model(model: str) -> bool:
    lowered = model.replace("\\", "/").lower()
    return "/straights/" in lowered and "trakpak" in lowered


def build_catalog(manifest_path: str | None = None) -> StraightCatalog:
    """Bake the straight list from ``data/trakpak3_models.json``."""

    manifest = load_manifest(manifest_path or DEFAULT_MANIFEST)
    pieces: list[StraightPiece] = []

    for model, entry in manifest["models"].items():
        if entry.get("family") != "straights":
            continue
        routes = entry.get("routes") or []
        if len(routes) != 1:
            continue
        parsed = parse_straight_name(model)
        if parsed is None:
            continue
        route = routes[0]
        move = tuple(int(round(v)) for v in route["Move"][:3])
        pieces.append(
            StraightPiece(
                model=model,
                direction=parsed["direction"],
                grade_token=parsed["grade_token"],
                real_grade=float(route["RealGrade"]),
                grade_level=int(route["GradeLevel"]),
                length=parsed["length"],
                move=move,
                change_y=parsed["change_y"],
                rise=int(move[2]),
            )
        )

    pieces.sort(key=lambda item: (item.direction, item.grade_token, item.length))

    by_key: dict[tuple[str, str, int], StraightPiece] = {}
    lengths_by_grade: dict[str, dict[str, list[int]]] = {}
    grade_info: dict[str, dict[str, StraightPiece]] = {}
    by_direction: dict[str, list[StraightPiece]] = {}

    for piece in pieces:
        by_key[(piece.direction, piece.grade_token, piece.length)] = piece
        lengths_by_grade.setdefault(piece.direction, {}).setdefault(
            piece.grade_token, []
        ).append(piece.length)
        grade_info.setdefault(piece.direction, {})[piece.grade_token] = piece
        by_direction.setdefault(piece.direction, []).append(piece)

    frozen_lengths = {
        direction: {
            grade: tuple(sorted(set(lengths), reverse=True))
            for grade, lengths in grades.items()
        }
        for direction, grades in lengths_by_grade.items()
    }

    return StraightCatalog(
        pieces=tuple(pieces),
        by_key=by_key,
        lengths_by_grade=frozen_lengths,
        grade_info=grade_info,
        by_direction={key: tuple(value) for key, value in by_direction.items()},
    )


def get_catalog(manifest_path: str | None = None) -> StraightCatalog:
    """Process-wide catalog. Pass a path only when pointing at another manifest."""

    global _CATALOG
    if manifest_path is not None:
        return build_catalog(manifest_path)
    if _CATALOG is None:
        _CATALOG = build_catalog()
    return _CATALOG


def reset_catalog() -> None:
    global _CATALOG
    _CATALOG = None


def catalog_summary(catalog: StraightCatalog | None = None) -> dict:
    """Compact view of baked grades / lengths (handy for debugging)."""

    catalog = catalog or get_catalog()
    out = {}
    for direction, grades in sorted(catalog.lengths_by_grade.items()):
        out[direction] = {}
        for token, lengths in sorted(grades.items()):
            info = catalog.grade_info[direction][token]
            out[direction][token] = {
                "real_grade": info.real_grade,
                "grade_level": info.grade_level,
                "rise_per_length": info.rise / info.length if info.length else 0,
                "lengths": list(lengths),
            }
    return out
