#!/usr/bin/env python3
"""
Contract test: registry.yaml must validate against intake/registry-contract.schema.json.

The schema is the contract the csbx CLI resolver pins against. A schema-breaking
change here will fail this test; if intentional, the schema and the resolver
must move together (see MIGRATIONS.md).

Also exercises break fixtures under tests/fixtures/contract/ to confirm the
schema actually rejects malformed inputs (a contract that accepts everything
is no contract at all).

Exit:
    0  registry conforms and break fixtures fail as expected
    1  contract drift, or a break fixture failed to fail
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print("[-] jsonschema not installed; run `pip install jsonschema`", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "intake" / "registry-contract.schema.json"
REGISTRY_PATH = ROOT / "registry.yaml"
BREAK_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "contract"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def check_main_registry(validator: Draft202012Validator) -> bool:
    errors = sorted(validator.iter_errors(load_yaml(REGISTRY_PATH)), key=lambda e: e.path)
    if not errors:
        print("[PASS] registry.yaml conforms to contract")
        return True
    print(f"[FAIL] registry.yaml has {len(errors)} contract violations:")
    for err in errors:
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        print(f"       {loc}: {err.message}")
    return False


def check_break_fixtures(validator: Draft202012Validator) -> bool:
    if not BREAK_FIXTURE_DIR.exists():
        print(f"[WARN] no break fixtures under {BREAK_FIXTURE_DIR}")
        return True
    fixtures = sorted(BREAK_FIXTURE_DIR.glob("*.yaml"))
    if not fixtures:
        print(f"[WARN] {BREAK_FIXTURE_DIR} is empty")
        return True

    ok = True
    for fixture in fixtures:
        data = load_yaml(fixture)
        registry = data["registry"]
        expect_violation_path = data.get("expect_violation_path", "")

        errors = list(validator.iter_errors(registry))
        if not errors:
            print(f"[FAIL] {fixture.name} should have failed validation but passed")
            ok = False
            continue

        if expect_violation_path:
            haystack = [
                f"{'/'.join(str(p) for p in e.absolute_path)}::{e.message}"
                for e in errors
            ]
            if not any(expect_violation_path in h for h in haystack):
                print(
                    f"[FAIL] {fixture.name} expected violation containing "
                    f"{expect_violation_path!r}, got: {haystack}"
                )
                ok = False
                continue
        print(f"[PASS] {fixture.name} rejected as expected")
    return ok


def main() -> int:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    main_ok = check_main_registry(validator)
    break_ok = check_break_fixtures(validator)
    return 0 if (main_ok and break_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
