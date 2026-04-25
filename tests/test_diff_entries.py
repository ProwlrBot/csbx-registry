#!/usr/bin/env python3
"""Tests for scripts/intake/diff-entries.py — replaces a yq pipeline that
broke on a yq lexer regression in newer releases."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "scripts" / "intake" / "diff-entries.py"

SAMPLE_YAML = """\
version: 1
policy_version: "2026-04-25"
pdtm_tools:
  ffuf:
    repo: ffuf/ffuf
    install_type: go
    go_install_path: github.com/ffuf/ffuf/v2
    version: latest
plugins:
  seclists:
    repo: https://github.com/danielmiessler/SecLists
    type: wordlist
    description: "Word lists"
    size: "1.2GB"
    tags: [recon]
caido_plugins: {}
"""


def write_tmp(text: str) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    f.write(text)
    f.close()
    return Path(f.name)


def run(args: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run([str(TOOL), *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def test_diff_against_empty_base() -> None:
    head = write_tmp(SAMPLE_YAML)
    base = write_tmp("")
    code, out, err = run(["--head", str(head), "--base", str(base)])
    assert code == 0, err
    data = json.loads(out)
    keys = sorted(e["key"] for e in data["include"])
    assert keys == ["ffuf", "seclists"]
    head.unlink()
    base.unlink()
    print("[PASS] diff against empty base lists all entries")


def test_diff_no_changes() -> None:
    head = write_tmp(SAMPLE_YAML)
    base = write_tmp(SAMPLE_YAML)
    code, out, _ = run(["--head", str(head), "--base", str(base)])
    assert code == 0
    data = json.loads(out)
    assert data["include"] == []
    head.unlink()
    base.unlink()
    print("[PASS] identical head and base => empty diff")


def test_diff_modified_entry() -> None:
    head_yaml = SAMPLE_YAML.replace("size: \"1.2GB\"", "size: \"1.5GB\"")
    head = write_tmp(head_yaml)
    base = write_tmp(SAMPLE_YAML)
    code, out, _ = run(["--head", str(head), "--base", str(base)])
    assert code == 0
    data = json.loads(out)
    assert len(data["include"]) == 1
    assert data["include"][0]["key"] == "seclists"
    head.unlink()
    base.unlink()
    print("[PASS] modified entry detected")


def test_only_flag() -> None:
    head = write_tmp(SAMPLE_YAML)
    code, out, _ = run(["--head", str(head), "--only", "plugins.seclists"])
    assert code == 0
    data = json.loads(out)
    assert len(data["include"]) == 1
    assert data["include"][0]["section"] == "plugins"
    assert data["include"][0]["key"] == "seclists"
    head.unlink()
    print("[PASS] --only flag selects single entry")


def test_only_flag_missing_entry() -> None:
    head = write_tmp(SAMPLE_YAML)
    code, out, _ = run(["--head", str(head), "--only", "plugins.nope"])
    assert code == 0
    data = json.loads(out)
    assert data["include"] == []
    head.unlink()
    print("[PASS] --only with missing key produces empty list")


def test_only_flag_accepts_slash_separator() -> None:
    # Workflow input format uses "<section>/<name>" — diff-entries should
    # normalize that to the internal "<section>.<name>" form.
    head = write_tmp(SAMPLE_YAML)
    code, out, _ = run(["--head", str(head), "--only", "plugins/seclists"])
    assert code == 0, out
    data = json.loads(out)
    assert len(data["include"]) == 1, f"expected 1 entry, got {data}"
    assert data["include"][0]["key"] == "seclists"
    head.unlink()
    print("[PASS] --only accepts slash separator")


def main() -> int:
    tests = [
        test_diff_against_empty_base,
        test_diff_no_changes,
        test_diff_modified_entry,
        test_only_flag,
        test_only_flag_missing_entry,
        test_only_flag_accepts_slash_separator,
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
