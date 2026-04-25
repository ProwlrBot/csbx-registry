#!/usr/bin/env python3
"""
Remove a single entry from registry.yaml in-place, preserving structure.

Usage:
    python3 scripts/intake/remove-entry.py --section <section> --name <name>

Used by the auto-removal workflow (feature-16) to script the removal half
of a stale-entry tracking issue. PyYAML's safe_dump reorders keys; we
preserve the document by editing on a line-range basis instead.

Exits:
    0 — entry removed; one line per affected entry written to stdout
    1 — entry not found, or invalid input
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


def find_entry_block(lines: list[str], section: str, name: str) -> tuple[int, int] | None:
    """Return (start_idx, end_idx_exclusive) of the entry's block in lines."""
    section_re = re.compile(rf"^{re.escape(section)}\s*:\s*(\{{.*\}})?\s*$")
    in_section = False
    section_indent = 0
    block_start = None
    block_indent = None

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if section_re.match(stripped):
            in_section = True
            section_indent = len(stripped) - len(stripped.lstrip(" "))
            continue
        if not in_section:
            continue
        # Section ends when we hit a top-level key (or EOF)
        leading = len(line) - len(line.lstrip(" "))
        if line.strip() and leading <= section_indent and not line.lstrip().startswith("#"):
            in_section = False
            continue
        # Inside the section: look for "<name>:" at indent > section_indent
        if block_start is None:
            m = re.match(rf"^(\s+){re.escape(name)}\s*:\s*$", stripped)
            if m:
                block_start = i
                block_indent = len(m.group(1))
            continue
        # Inside the entry block — end when indent drops back to <= block_indent
        if line.strip():
            leading = len(line) - len(line.lstrip(" "))
            if leading <= block_indent:
                return (block_start, i)

    if block_start is not None:
        # Entry runs to end-of-file
        return (block_start, len(lines))
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", default="registry.yaml")
    p.add_argument("--section", required=True,
                   choices=["pdtm_tools", "plugins", "caido_plugins"])
    p.add_argument("--name", required=True)
    args = p.parse_args()

    path = Path(args.registry)
    text = path.read_text()
    lines = text.splitlines(keepends=True)

    # Sanity-check the entry actually exists via parsed YAML
    parsed = yaml.safe_load(text) or {}
    if args.name not in (parsed.get(args.section) or {}):
        print(f"[-] entry {args.section}/{args.name} not found", file=sys.stderr)
        return 1

    block = find_entry_block(lines, args.section, args.name)
    if block is None:
        print(f"[-] could not locate text block for {args.section}/{args.name}", file=sys.stderr)
        return 1

    start, end = block
    # Trim trailing blank lines that immediately followed the entry
    while end < len(lines) and lines[end].strip() == "":
        end += 1

    new_text = "".join(lines[:start] + lines[end:])

    # Validate post-removal still parses and entry is gone
    new_parsed = yaml.safe_load(new_text) or {}
    if args.name in (new_parsed.get(args.section) or {}):
        print(f"[-] removal regex missed the entry — bailing", file=sys.stderr)
        return 1

    path.write_text(new_text)
    print(f"removed {args.section}/{args.name} (lines {start+1}-{end})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
