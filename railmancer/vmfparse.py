#!/usr/bin/env python3

"""
Split a Source Engine VMF file into:

    Start     - VMF header and world header, ending immediately before
                the first object inside world { ... }

    Brushes   - list of individual world solid { ... } blocks.
                Solids inside entities are excluded.
                Solids inside world/hidden { ... } are included.

    Entities  - list of individual entity blocks.
                A top-level hidden { entity { ... } } is preserved as
                one complete entry so the hidden state is not lost.

    End       - everything after the last top-level entity/hidden entity
                block, normally cameras/cordon/etc.

The parser deliberately does not use regular expressions to match
nested VMF blocks. VMF is a brace-delimited format, so this script
tracks the actual nesting structure.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Block:
    """A single VMF block and its location in the source text."""

    name: str
    start: int
    open_brace: int
    close_brace: int
    parent: int | None


@dataclass
class VMFSections:
    Start: str
    Brushes: list[str]
    Entities: list[str]
    End: str


def line_start(text: str, position: int) -> int:
    """Return the beginning of the line containing position."""
    return text.rfind("\n", 0, position) + 1


def parse_blocks(text: str) -> list[Block]:
    """
    Parse VMF block structure.

    A VMF block looks like:

        solid
        {
            ...
        }

    Quoted strings are ignored while looking for braces, so braces inside
    quoted values cannot accidentally alter the nesting level.

    // comments are also ignored.
    """

    blocks: list[Block] = []
    stack: list[int | None] = []

    pending_name: str | None = None
    pending_start: int | None = None

    in_string = False
    escaped = False
    currently_in_comment = False

    identifier_start: int | None = None

    character_index_number = 0
    overall_character_length = len(text)

    while character_index_number < overall_character_length:
        current_character = text[character_index_number]

        # ------------------------------------------------------------
        # Inside a // comment
        # ------------------------------------------------------------
        if currently_in_comment:
            if current_character == "\n":
                currently_in_comment = False
            character_index_number += 1
            continue

        # ------------------------------------------------------------
        # Inside a quoted string
        # ------------------------------------------------------------
        if in_string:
            if escaped:
                escaped = False
            elif current_character == "\\":
                escaped = True
            elif current_character == '"':
                in_string = False

            character_index_number += 1
            continue

        # ------------------------------------------------------------
        # Start of comment
        # ------------------------------------------------------------
        if (
            current_character == "/"
            and character_index_number + 1 < overall_character_length
            and text[character_index_number + 1] == "/"
        ):
            if identifier_start is not None:
                identifier_start = None

            currently_in_comment = True
            character_index_number += 2
            continue

        # ------------------------------------------------------------
        # Start/end of quoted string
        # ------------------------------------------------------------
        if current_character == '"':
            if identifier_start is not None:
                identifier_start = None

            in_string = True
            character_index_number += 1
            continue

        # ------------------------------------------------------------
        # Identifier
        # ------------------------------------------------------------
        if current_character.isalpha() or current_character == "_":
            if identifier_start is None:
                identifier_start = character_index_number

        else:
            # We just finished an identifier.
            if identifier_start is not None:
                name = text[identifier_start:character_index_number]

                # See whether the next non-whitespace character is "{"
                j = character_index_number
                while j < overall_character_length and text[j].isspace():
                    j += 1

                if j < overall_character_length and text[j] == "{":
                    pending_name = name
                    pending_start = identifier_start

                identifier_start = None

        # ------------------------------------------------------------
        # Opening brace
        # ------------------------------------------------------------
        if current_character == "{":
            if pending_name is not None:
                parent = stack[-1] if stack else None

                block = Block(
                    name=pending_name,
                    start=pending_start,
                    open_brace=character_index_number,
                    close_brace=-1,
                    parent=parent,
                )

                block_index = len(blocks)
                blocks.append(block)
                stack.append(block_index)

                pending_name = None
                pending_start = None

            else:
                # An unnamed brace. This should not normally occur in VMF,
                # but keeping it on the stack makes the parser tolerant.
                stack.append(None)

        # ------------------------------------------------------------
        # Closing brace
        # ------------------------------------------------------------
        elif current_character == "}":
            if stack:
                block_index = stack.pop()

                if block_index is not None:
                    blocks[block_index].close_brace = character_index_number

        character_index_number += 1

    return blocks


def get_ancestors(blocks: list[Block], index: int):
    """Yield block index followed by all of its parents."""
    current = index

    while current is not None:
        yield current
        current = blocks[current].parent


def has_ancestor(
    blocks: list[Block],
    index: int,
    target_indices: set[int],
) -> bool:
    """Return True if a block has one of target_indices as an ancestor."""
    for ancestor in get_ancestors(blocks, index):
        if ancestor in target_indices:
            return True

    return False


def split_vmf(filename: str | Path) -> VMFSections:
    """
    Read a VMF file and return Start, Brushes, Entities, and End.
    """

    path = Path(filename)

    # newline="" is intentional: preserve the VMF's original line endings.
    with path.open("r", encoding="utf-8", newline="") as f:
        text = f.read()

    blocks = parse_blocks(text)

    if not blocks:
        raise ValueError("The VMF file contains no recognizable blocks.")

    # ------------------------------------------------------------
    # Locate the top-level world block.
    # ------------------------------------------------------------

    world_indices = [
        character_index_number
        for character_index_number, block in enumerate(blocks)
        if block.name == "world" and block.parent is None
    ]

    if len(world_indices) != 1:
        raise ValueError(
            f"Expected exactly one top-level world block, "
            f"found {len(world_indices)}."
        )

    world_index = world_indices[0]
    world = blocks[world_index]

    # ------------------------------------------------------------
    # START
    #
    # Everything before the first child of world is the VMF header.
    # The world header itself is included.
    #
    # For the supplied VMF this ends immediately after:
    #
    #     "skyname" "sky_gravel_01"
    #
    # and immediately before the first solid.
    # ------------------------------------------------------------

    world_children = [block for block in blocks if block.parent == world_index]

    if world_children:
        first_world_child = min(
            world_children,
            key=lambda block: block.start,
        )

        start_end = line_start(text, first_world_child.start)
        Start = text[:start_end]
    else:
        # A world with no contents.
        start_end = line_start(text, world.close_brace)
        Start = text[:start_end]

    # ------------------------------------------------------------
    # BRUSHES
    #
    # A solid belongs to Brushes if:
    #
    #   1. It is somewhere inside world { ... }
    #   2. It is NOT inside an entity.
    #
    # This automatically handles:
    #
    #     world
    #     {
    #         solid { ... }
    #
    #         hidden
    #         {
    #             solid { ... }
    #         }
    #     }
    #
    # while excluding:
    #
    #     entity
    #     {
    #         solid { ... }
    #     }
    # ------------------------------------------------------------

    entity_indices = {
        character_index_number
        for character_index_number, block in enumerate(blocks)
        if block.name == "entity"
    }

    brushes: list[Block] = []

    for character_index_number, block in enumerate(blocks):
        if block.name != "solid":
            continue

        # Must be inside world.
        if not has_ancestor(blocks, character_index_number, {world_index}):
            continue

        # A solid belonging to an entity is an entity solid, not a
        # world brush.
        if has_ancestor(blocks, character_index_number, entity_indices):
            continue

        brushes.append(block)

    # Preserve original file order.
    brushes.sort(key=lambda block: block.start)

    Brushes = [
        text[line_start(text, block.start) : block.close_brace + 1] for block in brushes
    ]

    # ------------------------------------------------------------
    # ENTITIES
    #
    # Normal VMFs have:
    #
    #     entity { ... }
    #     entity { ... }
    #
    # at the top level.
    #
    # Some VMFs can instead have:
    #
    #     hidden
    #     {
    #         entity
    #         {
    #             ...
    #         }
    #     }
    #
    # In that case we preserve the COMPLETE hidden block rather than
    # stripping the hidden wrapper away.
    # ------------------------------------------------------------

    entity_entries: list[Block] = []

    # Ordinary top-level entities.
    for character_index_number, block in enumerate(blocks):
        if block.name == "entity" and block.parent is None:
            entity_entries.append(block)

    # Top-level hidden blocks containing entities.
    #
    # We deliberately preserve the hidden wrapper.
    for character_index_number, block in enumerate(blocks):
        if block.name != "hidden" or block.parent is not None:
            continue

        contains_entity = any(
            child_index != character_index_number
            and child_block.name == "entity"
            and has_ancestor(blocks, child_index, {character_index_number})
            for child_index, child_block in enumerate(blocks)
        )

        if contains_entity:
            entity_entries.append(block)

    # Remove duplicates and preserve file order.
    entity_entries = list({block.start: block for block in entity_entries}.values())

    entity_entries.sort(key=lambda block: block.start)

    Entities = [
        text[line_start(text, block.start) : block.close_brace + 1]
        for block in entity_entries
    ]

    # ------------------------------------------------------------
    # END
    #
    # Everything after the final top-level entity/hidden entity is
    # preserved verbatim.
    #
    # In the supplied file this gives:
    #
    #     cameras
    #     {
    #         ...
    #     }
    #     cordon
    #     {
    #         ...
    #     }
    # ------------------------------------------------------------

    if entity_entries:
        last_entity = max(
            entity_entries,
            key=lambda block: block.close_brace,
        )

        end_start = line_start(text, last_entity.close_brace + 1)

    else:
        # No entities: start immediately after world.
        end_start = line_start(text, world.close_brace + 1)

    End = text[end_start:]

    return VMFSections(
        Start=Start,
        Brushes=Brushes,
        Entities=Entities,
        End=End,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Split a Source Engine VMF into Start, Brushes, Entities, and End."
    )

    parser.add_argument(
        "vmf",
        help="Input VMF file",
    )

    parser.add_argument(
        "--show-counts",
        action="store_true",
        help="Print the number of extracted brushes and entities.",
    )

    args = parser.parse_args()

    sections = split_vmf(args.vmf)

    # These variables now contain exactly the requested structures:
    Start = sections.Start
    Brushes = sections.Brushes
    Entities = sections.Entities
    End = sections.End

    if args.show_counts:
        print(f"Brushes:  {len(Brushes)}")
        print(f"Entities: {len(Entities)}")
        print(f"Start:    {len(Start):,} characters")
        print(f"End:      {len(End):,} characters")

    # ------------------------------------------------------------
    # If you want to use the variables from another Python program,
    # import split_vmf() instead of using this command-line section.
    #
    # Example:
    #
    #     sections = split_vmf("gm_industry.vmf")
    #
    #     Start = sections.Start
    #     Brushes = sections.Brushes
    #     Entities = sections.Entities
    #     End = sections.End
    # ------------------------------------------------------------


if __name__ == "__main__":
    main()
