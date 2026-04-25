#!/usr/bin/env python3
"""
Detect entries added or modified in the PR's registry.yaml relative to base.

Replaces a bash+yq+jq pipeline in .github/workflows/intake.yml (which broke
on a yq lexer regression in newer releases). Pure Python + PyYAML — no
shelling out, no version drift.

Inputs:
    --head PATH     PR head's registry.yaml (default: registry.yaml)
    --base PATH     base branch's registry.yaml (defaults to empty if absent)
    --only KEY      restrict to a single "<section>.<name>" entry (used by
                    the persist-attestations workflow's manual dispatch)

Output (stdout): JSON object with "include" key containing a list of
{key, section, entry} dicts — the matrix shape GH Actions expects.

Also writes:
    GITHUB_OUTPUT="matrix=<json>\\ncount=<n>\\n" if GITHUB_OUTPUT env set
    (so it can be `run:`-ed as a single step in the workflow).

Exits:
    0 — diff produced (count may be 0)
    1 — input invariant violated
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

SECTIONS = ("pdtm_tools", "plugins", "caido_plugins")


def flatten(data: dict | None) -> dict:
    """Return {"<section>.<name>": <entry>} across all known sections."""
    flat: dict = {}
    if not data:
        return flat
    for section in SECTIONS:
        block = data.get(section) or {}
        if not isinstance(block, dict):
            continue
        for name, entry in block.items():
            flat[f"{section}.{name}"] = entry
    return flat


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--head", default="registry.yaml")
    p.add_argument("--base", default="")
    p.add_argument("--only", default="")
    args = p.parse_args()

    head = flatten(load(Path(args.head)))
    base = flatten(load(Path(args.base))) if args.base else {}

    changed: list[dict] = []
    if args.only:
        # Accept both "<section>.<name>" (internal) and "<section>/<name>"
        # (user-facing, matches the workflow input description). Normalize.
        only_key = args.only.replace("/", ".", 1)
        if only_key in head:
            section, _, name = only_key.partition(".")
            changed.append({"key": name, "section": section, "entry": head[only_key]})
    else:
        for full_key, entry in head.items():
            if base.get(full_key) == entry:
                continue
            section, _, name = full_key.partition(".")
            changed.append({"key": name, "section": section, "entry": entry})

    matrix = {"include": changed}
    matrix_json = json.dumps(matrix, separators=(",", ":"))
    count = len(changed)

    print(json.dumps(matrix, indent=2))

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"matrix={matrix_json}\n")
            f.write(f"count={count}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
