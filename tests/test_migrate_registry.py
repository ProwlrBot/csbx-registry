#!/usr/bin/env python3
"""Smoke tests for scripts/intake/migrate-registry.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "scripts" / "intake" / "migrate-registry.py"


def run(args: list[str], stdin_text: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(TOOL), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_identity_migration_stdio() -> None:
    src = "version: 1\npolicy_version: '2026-04-25'\npdtm_tools: {}\nplugins: {}\ncaido_plugins: {}\n"
    code, out, err = run(["--from", "1", "--to", "1"], stdin_text=src)
    assert code == 0, f"exit {code}\nstderr: {err}"
    parsed = yaml.safe_load(out)
    assert parsed["version"] == 1
    assert parsed["policy_version"] == "2026-04-25"
    print("[PASS] identity migration via stdin/stdout")


def test_identity_migration_files() -> None:
    src = "version: 1\npolicy_version: '2026-04-25'\npdtm_tools: {}\nplugins: {}\ncaido_plugins: {}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(src)
        in_path = f.name
    out_path = in_path + ".out"
    code, _, err = run(["--from", "1", "--to", "1", "--in", in_path, "--out", out_path])
    assert code == 0, f"exit {code}\nstderr: {err}"
    parsed = yaml.safe_load(Path(out_path).read_text())
    assert parsed["version"] == 1
    Path(in_path).unlink()
    Path(out_path).unlink()
    print("[PASS] identity migration via --in/--out")


def test_version_mismatch_rejects() -> None:
    src = "version: 9\npolicy_version: '2026-04-25'\n"
    code, _, err = run(["--from", "1", "--to", "1"], stdin_text=src)
    assert code == 1
    assert "version is 9" in err
    print("[PASS] mismatched --from rejected")


def test_unknown_step_rejects() -> None:
    src = "version: 1\npolicy_version: '2026-04-25'\n"
    code, _, err = run(["--from", "1", "--to", "5"], stdin_text=src)
    assert code == 1
    assert "no migration step" in err
    print("[PASS] unknown 1->5 step rejected")


def main() -> int:
    tests = [
        test_identity_migration_stdio,
        test_identity_migration_files,
        test_version_mismatch_rejects,
        test_unknown_step_rejects,
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
