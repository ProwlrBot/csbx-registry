#!/usr/bin/env python3
"""
Manifest-level validator for csbx-registry.

Checks:
- `version` is in SUPPORTED_VERSIONS (with a deprecation warning for older ones).
- `policy_version` is present and not older than the base branch's value.

Env vars:
    REGISTRY_FILE       path to the PR's registry.yaml (default: registry.yaml)
    BASE_REGISTRY_FILE  path to main's registry.yaml (optional; skips comparison if absent)

Writes to stdout:
    {"check":"manifest","status":"pass|fail","details":{...},"blocking":true}

Exits:
    0 — pass (deprecation warning on stderr does not fail)
    1 — fail
"""
from __future__ import annotations

import json
import os
import sys

import yaml

# Schemas accepted by intake. The newest is always the head of this set.
SUPPORTED_VERSIONS = {1}
# Schemas still accepted but emitting a deprecation warning. See MIGRATIONS.md.
DEPRECATED_VERSIONS: set[int] = set()


def emit(status: str, details: dict) -> None:
    print(json.dumps({"check": "manifest", "status": status, "details": details, "blocking": True}))


def fail(msg: str, **extra) -> None:
    print(f"[-] manifest: {msg}", file=sys.stderr)
    emit("fail", {"error": msg, **extra})
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"[!] manifest: {msg}", file=sys.stderr)


def load(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def main() -> None:
    registry_path = os.environ.get("REGISTRY_FILE", "registry.yaml")
    base_path = os.environ.get("BASE_REGISTRY_FILE", "")

    try:
        head = load(registry_path)
    except Exception as e:
        fail(f"cannot load {registry_path}: {e}")

    version = head.get("version")
    if not isinstance(version, int):
        fail("version is missing or not an integer", registry=registry_path)
    if version not in SUPPORTED_VERSIONS and version not in DEPRECATED_VERSIONS:
        fail(
            f"version={version} is not supported",
            supported=sorted(SUPPORTED_VERSIONS),
            deprecated=sorted(DEPRECATED_VERSIONS),
        )
    if version in DEPRECATED_VERSIONS:
        warn(f"version={version} is deprecated; see MIGRATIONS.md for the migration path")

    pv = head.get("policy_version")
    if not pv or not isinstance(pv, str):
        fail("policy_version is missing or not a string", registry=registry_path)

    if base_path:
        try:
            base = load(base_path)
        except Exception as e:
            fail(f"cannot load base registry {base_path}: {e}")

        base_pv = base.get("policy_version", "")
        if pv < str(base_pv):
            fail(
                "policy_version must not decrease",
                head=pv,
                base=str(base_pv),
            )

    emit("pass", {"version": version, "policy_version": pv})


if __name__ == "__main__":
    main()
