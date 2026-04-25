#!/usr/bin/env python3
"""Smoke tests for tools/prefetch.py — exercises planning logic without network."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "prefetch.py"


def test_dry_run_against_real_registry() -> None:
    proc = subprocess.run(
        [str(TOOL), "--dry-run", "--cache", "/tmp/test-prefetch-cache", "--only", "plugins"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"exit {proc.returncode}\nstderr: {proc.stderr}"
    assert "[*] plugins/seclists" in proc.stdout, "expected SecLists planned"
    assert "Planned" in proc.stdout
    print("[PASS] dry-run against registry.yaml plugins section")


def test_dry_run_caido_section_empty() -> None:
    proc = subprocess.run(
        [str(TOOL), "--dry-run", "--cache", "/tmp/test-prefetch-cache", "--only", "caido_plugins"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "Planned 0 files" in proc.stdout
    print("[PASS] dry-run against empty caido_plugins section")


def test_invalid_section_rejected() -> None:
    proc = subprocess.run(
        [str(TOOL), "--dry-run", "--only", "nonexistent"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    print("[PASS] invalid --only section rejected")


def main() -> int:
    tests = [
        test_dry_run_against_real_registry,
        test_dry_run_caido_section_empty,
        test_invalid_section_rejected,
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
