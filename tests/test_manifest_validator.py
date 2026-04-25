#!/usr/bin/env python3
"""Tests for scripts/intake/validate-manifest.py."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "intake" / "validate-manifest.py"


def run(registry: str, base: str | None = None) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(registry)
        registry_path = f.name
    base_path = None
    if base is not None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(base)
            base_path = f.name
    try:
        env = {**os.environ, "REGISTRY_FILE": registry_path}
        if base_path:
            env["BASE_REGISTRY_FILE"] = base_path
        proc = subprocess.run(
            [str(VALIDATOR)],
            env=env,
            capture_output=True,
            text=True,
        )
        return proc.returncode, proc.stdout + proc.stderr
    finally:
        os.unlink(registry_path)
        if base_path:
            os.unlink(base_path)


MINIMAL_HEAD = """\
version: 1
policy_version: "2026-04-25"
updated: "2026-04-25"
"""

MINIMAL_HEAD_OLD = """\
version: 1
policy_version: "2026-01-01"
updated: "2026-04-25"
"""

MINIMAL_HEAD_NEWER = """\
version: 1
policy_version: "2026-05-01"
updated: "2026-04-25"
"""

MISSING_POLICY_VERSION = """\
version: 1
updated: "2026-04-25"
"""

BASE = """\
version: 1
policy_version: "2026-04-25"
updated: "2026-04-25"
"""


def test_missing_policy_version() -> None:
    code, out = run(MISSING_POLICY_VERSION)
    assert code == 1, f"expected exit 1, got {code}\noutput: {out}"
    assert "policy_version" in out, f"expected 'policy_version' in output\noutput: {out}"
    print("[PASS] missing policy_version -> exit 1")


def test_present_policy_version() -> None:
    code, out = run(MINIMAL_HEAD)
    assert code == 0, f"expected exit 0, got {code}\noutput: {out}"
    print("[PASS] present policy_version -> exit 0")


def test_older_head_than_base() -> None:
    code, out = run(MINIMAL_HEAD_OLD, base=BASE)
    assert code == 1, f"expected exit 1, got {code}\noutput: {out}"
    assert "policy_version" in out, f"expected 'policy_version' in output\noutput: {out}"
    print("[PASS] head policy_version older than base -> exit 1")


def test_newer_head_than_base() -> None:
    code, out = run(MINIMAL_HEAD_NEWER, base=BASE)
    assert code == 0, f"expected exit 0, got {code}\noutput: {out}"
    print("[PASS] head policy_version newer than base -> exit 0")


def main() -> int:
    tests = [
        test_missing_policy_version,
        test_present_policy_version,
        test_older_head_than_base,
        test_newer_head_than_base,
    ]
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failures += 1
    print(f"\nSummary: {len(tests) - failures} passed, {failures} failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
