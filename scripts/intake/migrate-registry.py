#!/usr/bin/env python3
"""
Mechanical migration tool for registry.yaml between schema versions.

Usage:
    python3 scripts/intake/migrate-registry.py --from N --to M < registry.yaml > new.yaml

Or read from a file:
    python3 scripts/intake/migrate-registry.py --from N --to M --in registry.yaml --out new.yaml

Each migration step is a function `migrate_<from>_to_<to>(data: dict) -> dict`.
Steps must be:
- pure (no network, no I/O)
- idempotent (re-running the same step on already-migrated data is a no-op)
- targeted (only touch what the migration actually changes)

When a new step lands, append it to MIGRATIONS.md and to the STEPS dict below.

Exits:
    0 — migration succeeded
    1 — invalid invocation, unknown step, or input shape unsupported
"""
from __future__ import annotations

import argparse
import sys
from typing import Callable

import yaml


def migrate_1_to_1(data: dict) -> dict:
    """No-op identity migration. Useful as a smoke test for the framework."""
    return data


# Add steps here as {(from_version, to_version): step_fn}.
STEPS: dict[tuple[int, int], Callable[[dict], dict]] = {
    (1, 1): migrate_1_to_1,
}


def chain(from_version: int, to_version: int) -> list[Callable[[dict], dict]]:
    """Return the ordered list of step functions to walk from→to."""
    if from_version == to_version:
        return [STEPS[(from_version, to_version)]]
    steps: list[Callable[[dict], dict]] = []
    cur = from_version
    while cur < to_version:
        nxt = cur + 1
        if (cur, nxt) not in STEPS:
            raise SystemExit(f"no migration step registered for {cur} -> {nxt}")
        steps.append(STEPS[(cur, nxt)])
        cur = nxt
    return steps


def main() -> int:
    p = argparse.ArgumentParser(description="Migrate registry.yaml between schema versions")
    p.add_argument("--from", dest="from_version", type=int, required=True)
    p.add_argument("--to", dest="to_version", type=int, required=True)
    p.add_argument("--in", dest="in_path", default=None)
    p.add_argument("--out", dest="out_path", default=None)
    args = p.parse_args()

    if args.from_version > args.to_version:
        print(f"[-] migrate: --from {args.from_version} > --to {args.to_version}", file=sys.stderr)
        return 1

    src = open(args.in_path) if args.in_path else sys.stdin
    data = yaml.safe_load(src.read()) or {}
    if args.in_path:
        src.close()

    actual = data.get("version")
    if actual != args.from_version:
        print(
            f"[-] migrate: registry version is {actual}, expected --from {args.from_version}",
            file=sys.stderr,
        )
        return 1

    for step in chain(args.from_version, args.to_version):
        data = step(data)

    out = open(args.out_path, "w") if args.out_path else sys.stdout
    yaml.safe_dump(data, out, sort_keys=False)
    if args.out_path:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
