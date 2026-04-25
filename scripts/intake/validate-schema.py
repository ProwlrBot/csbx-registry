#!/usr/bin/env python3
"""
Schema validator for csbx-registry entries.

Usage:
    ENTRY_NAME=my-plugin ENTRY_JSON='{...}' SECTION=caido_plugins ./validate-schema.py

Reads:
    ENTRY_NAME  — the registry key (e.g. "my-caido-plugin")
    ENTRY_JSON  — the entry value as a JSON string
    SECTION     — "caido_plugins" or one of the existing plugins.* sections

Writes to stdout:
    {"check": "schema", "status": "pass"|"fail", "details": {...}, "blocking": true}

Exits:
    0 — pass
    1 — fail (blocking)
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

SUPPORTED_TYPES = {
    "tool",
    "wordlist",
    "nuclei-templates",
    "yara-rules",
    "sigma",
    "threat-intel",
    "theme",
    "config",
    "caido-plugin",
}

REQUIRED_BASE_FIELDS = ("repo", "type", "description", "size", "tags")
REQUIRED_CAIDO_FIELDS = ("release", "manifest", "signature")
SUPPORTED_SIG_METHODS = {"cosign", "minisign"}
SUPPORTED_PLATFORMS = {
    "linux-amd64", "linux-arm64",
    "darwin-amd64", "darwin-arm64",
    "windows-amd64", "windows-arm64",
}

# Multi-forge: github, gitlab, codeberg. See scripts/intake/forge_adapter.py
# for the canonical list — this regex is duplicated here only to avoid a
# Python import in the per-entry validator.
SUPPORTED_REPO_RE = re.compile(
    r"^https://(?:github\.com|gitlab\.com|codeberg\.org)/[^/\s]+/[^/\s]+/?$"
)


def emit(status: str, details: dict[str, Any], blocking: bool = True) -> None:
    print(json.dumps({
        "check": "schema",
        "status": status,
        "details": details,
        "blocking": blocking,
    }))


def fail(msg: str, **extra: Any) -> None:
    print(f"[-] schema: {msg}", file=sys.stderr)
    emit("fail", {"error": msg, **extra})
    sys.exit(1)


def main() -> None:
    name = os.environ.get("ENTRY_NAME")
    raw = os.environ.get("ENTRY_JSON")
    section = os.environ.get("SECTION", "")

    if not name or not raw:
        fail("ENTRY_NAME and ENTRY_JSON env vars are required")

    try:
        entry = json.loads(raw)
    except json.JSONDecodeError as e:
        fail(f"ENTRY_JSON is not valid JSON: {e}")

    if not isinstance(entry, dict):
        fail(f"entry {name!r} must be a mapping, got {type(entry).__name__}")

    missing = [f for f in REQUIRED_BASE_FIELDS if f not in entry]
    if missing:
        fail(f"entry {name!r} missing required fields: {missing}", missing=missing)

    if entry["type"] not in SUPPORTED_TYPES:
        fail(
            f"entry {name!r} has unsupported type {entry['type']!r}",
            supported=sorted(SUPPORTED_TYPES),
        )

    if not isinstance(entry["repo"], str) or not SUPPORTED_REPO_RE.match(entry["repo"]):
        fail(
            f"entry {name!r} repo URL must point at a supported forge "
            f"(github.com / gitlab.com / codeberg.org)",
            repo=entry["repo"],
        )

    if not isinstance(entry["tags"], list) or not entry["tags"]:
        fail(f"entry {name!r} tags must be a non-empty list")

    if not isinstance(entry["description"], str) or len(entry["description"]) < 10:
        fail(f"entry {name!r} description must be at least 10 characters")

    if "platforms" in entry:
        platforms = entry["platforms"]
        if not isinstance(platforms, list) or not platforms:
            fail(f"entry {name!r} platforms must be a non-empty list when set")
        invalid = [p for p in platforms if p not in SUPPORTED_PLATFORMS]
        if invalid:
            fail(
                f"entry {name!r} declares unsupported platforms: {invalid}",
                supported=sorted(SUPPORTED_PLATFORMS),
            )

    if entry["type"] == "caido-plugin":
        if section != "caido_plugins":
            fail(
                f"caido-plugin entries must live under the caido_plugins section, "
                f"got section={section!r}",
            )

        cmissing = [f for f in REQUIRED_CAIDO_FIELDS if f not in entry]
        if cmissing:
            fail(
                f"caido-plugin {name!r} missing required fields: {cmissing}",
                missing=cmissing,
            )

        sig = entry["signature"]
        if not isinstance(sig, dict):
            fail(f"caido-plugin {name!r} signature must be a mapping")
        if sig.get("method") not in SUPPORTED_SIG_METHODS:
            fail(
                f"caido-plugin {name!r} signature.method must be one of {SUPPORTED_SIG_METHODS}",
                got=sig.get("method"),
            )
        if sig["method"] == "cosign":
            for k in ("issuer", "identity"):
                if k not in sig or not isinstance(sig[k], str):
                    fail(f"caido-plugin {name!r} signature.{k} required for cosign")
        elif sig["method"] == "minisign":
            if "public_key" not in sig or not isinstance(sig["public_key"], str):
                fail(f"caido-plugin {name!r} signature.public_key required for minisign")

    emit("pass", {"name": name, "type": entry["type"], "section": section})


if __name__ == "__main__":
    main()
