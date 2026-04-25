#!/usr/bin/env bash
# Offline intake test harness — runs the schema validator against every
# fixture under tests/fixtures/ and asserts behavior.
#
# This wrapper just hands off to tests/run_intake.py; both forms exist so
# the README example (./tests/run-intake.sh) keeps working.
set -euo pipefail
exec python3 "$(dirname "$0")/run_intake.py" "$@"
