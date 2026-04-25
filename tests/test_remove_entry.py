#!/usr/bin/env python3
"""Tests for scripts/intake/remove-entry.py — used by the auto-removal workflow."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "scripts" / "intake" / "remove-entry.py"
REGISTRY = ROOT / "registry.yaml"


def with_temp_registry() -> Path:
    tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    tmp.close()
    shutil.copyfile(REGISTRY, tmp.name)
    return Path(tmp.name)


def test_removes_existing_plugin_entry() -> None:
    tmp = with_temp_registry()
    proc = subprocess.run(
        [str(TOOL), "--registry", str(tmp), "--section", "plugins", "--name", "leaky-paths"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"exit {proc.returncode}\n{proc.stderr}"
    data = yaml.safe_load(tmp.read_text())
    assert "leaky-paths" not in data["plugins"]
    assert "seclists" in data["plugins"]      # adjacent entries unaffected
    assert "version" in data                  # top-level fields preserved
    tmp.unlink()
    print("[PASS] removes existing plugin entry; siblings preserved")


def test_rejects_missing_entry() -> None:
    tmp = with_temp_registry()
    proc = subprocess.run(
        [str(TOOL), "--registry", str(tmp), "--section", "plugins", "--name", "does-not-exist"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "not found" in proc.stderr
    tmp.unlink()
    print("[PASS] rejects missing entry")


def test_removes_pdtm_entry() -> None:
    tmp = with_temp_registry()
    proc = subprocess.run(
        [str(TOOL), "--registry", str(tmp), "--section", "pdtm_tools", "--name", "ffuf"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = yaml.safe_load(tmp.read_text())
    assert "ffuf" not in data["pdtm_tools"]
    assert "subfinder" in data["pdtm_tools"]
    tmp.unlink()
    print("[PASS] removes pdtm_tools entry")


def main() -> int:
    tests = [
        test_removes_existing_plugin_entry,
        test_rejects_missing_entry,
        test_removes_pdtm_entry,
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
