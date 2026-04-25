#!/usr/bin/env python3
"""Smoke tests for tools/generate-index.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "generate-index.py"


def run_tool(out_path: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(TOOL), "--out", str(out_path)],
        cwd=ROOT, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_index_generates_against_real_registry() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        out = Path(f.name)
    code, stdout, stderr = run_tool(out)
    assert code == 0, f"exit {code}\nstderr: {stderr}"
    content = out.read_text()
    out.unlink()

    assert "# csbx-registry catalog" in content, "missing header"
    assert "## pdtm tools" in content, "missing pdtm section"
    assert "subfinder" in content, "missing subfinder"
    assert "SecLists" in content or "seclists" in content, "missing seclists"
    assert "Caido plugins" in content, "missing caido section header"
    print("[PASS] INDEX.md generated with all expected sections")


def test_index_is_deterministic() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f1:
        out1 = Path(f1.name)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f2:
        out2 = Path(f2.name)
    run_tool(out1)
    run_tool(out2)
    a, b = out1.read_text(), out2.read_text()
    out1.unlink()
    out2.unlink()
    assert a == b, "two runs produced different output (not deterministic)"
    print("[PASS] generation is byte-deterministic")


def main() -> int:
    tests = [test_index_generates_against_real_registry, test_index_is_deterministic]
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
