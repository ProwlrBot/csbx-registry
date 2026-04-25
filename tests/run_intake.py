#!/usr/bin/env python3
"""
Offline intake test harness.

Runs scripts/intake/validate-schema.py against every fixture under
tests/fixtures/, asserts the actual exit code matches expect_exit (default 0),
and (if expect_error_contains is set) checks that the error output contains
the expected substring.

Network-dependent checks (repo accessibility, SBOM, SAST, signature) are not
exercised here — those run live in the GitHub Actions intake workflow. The
fixture-level guarantee is that schema-layer rejection works deterministically
without any external tooling.

Exit:
    0  all fixtures behaved as expected
    1  one or more fixtures behaved unexpectedly
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "tests" / "fixtures"
VALIDATOR = ROOT / "scripts" / "intake" / "validate-schema.py"


def run_fixture(fixture: Path) -> tuple[bool, str] | None:
    data = yaml.safe_load(fixture.read_text())
    section = data["section"]
    if section.startswith("_"):
        return None  # manifest-level fixtures; not exercised by per-entry harness
    key = data["key"]
    entry = data["entry"]
    expect_exit = int(data.get("expect_exit", 0))
    expect_substr = data.get("expect_error_contains", "")

    proc = subprocess.run(
        [str(VALIDATOR)],
        env={
            **os.environ,
            "ENTRY_NAME": key,
            "ENTRY_JSON": json.dumps(entry),
            "SECTION": section,
        },
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr

    if proc.returncode != expect_exit:
        return False, (
            f"exit code mismatch: expected={expect_exit} actual={proc.returncode}\n"
            f"  output: {output.strip()}"
        )
    if expect_substr and expect_substr not in output:
        return False, (
            f"expected error substring not found: {expect_substr!r}\n"
            f"  output: {output.strip()}"
        )
    return True, output.strip()


def main() -> int:
    fixtures = sorted(FIXTURE_DIR.glob("*.yaml"))
    if not fixtures:
        print(f"[-] no fixtures found under {FIXTURE_DIR}", file=sys.stderr)
        return 1

    pass_count = 0
    fail_count = 0
    print("=== Intake fixture results ===")
    for fixture in fixtures:
        name = fixture.stem
        result = run_fixture(fixture)
        if result is None:
            print(f"[SKIP] {name}")
            continue
        ok, detail = result
        if ok:
            pass_count += 1
            print(f"[PASS] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")
            for line in detail.splitlines():
                print(f"       {line}")

    print(f"\nSummary: {pass_count} passed, {fail_count} failed")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
