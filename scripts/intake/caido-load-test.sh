#!/usr/bin/env bash
# Behavioral / live-load test harness for caido-plugin entries.
#
# This is the SCAFFOLD. The real implementation requires a Caido binary in
# the runner image, which the project does not currently distribute (Caido
# does not publish a CI-friendly container image at the time of writing).
# The scaffold exists so:
#
# 1. The intake workflow has a defined job slot to call when a binary
#    becomes available — wiring the runtime later is plug-in.
# 2. Plugin authors can opt into the harness today (`behavioral_test: true`)
#    and the run will be a documented skip rather than an unknown.
# 3. POLICY.md and CONTRIBUTING.md can describe the harness contract
#    independently of when it ships.
#
# Inputs (env):
#   ENTRY_NAME, ENTRY_JSON
#   CACHED_REPO_DIR              path to the pre-cloned repo (from F14 cache)
#   CAIDO_BINARY_AVAILABLE       set to "true" by the workflow when a Caido
#                                binary is present on the runner
#   CAIDO_LOAD_TEST_OUT_DIR      where to write the outcome JSON (default ./caido-out)
#
# Output (stdout): JSON line {"check":"behavioral","status":"...","blocking":false}
# Exits: 0 always (this is informational — never blocks merge per POLICY.md)
set -euo pipefail

CAIDO_LOAD_TEST_OUT_DIR="${CAIDO_LOAD_TEST_OUT_DIR:-./caido-out}"
mkdir -p "$CAIDO_LOAD_TEST_OUT_DIR"

emit() {
  local status="$1" details="$2"
  printf '{"check":"behavioral","status":"%s","details":%s,"blocking":false}\n' \
    "$status" "$details"
}

: "${ENTRY_NAME:?}"
: "${ENTRY_JSON:?}"

type=$(jq -r '.type' <<<"$ENTRY_JSON")
opt_in=$(jq -r '.behavioral_test // false' <<<"$ENTRY_JSON")

if [[ "$type" != "caido-plugin" ]]; then
  emit "skip" "$(jq -nc --arg t "$type" '{reason:"non-caido type",type:$t}')"
  exit 0
fi

if [[ "$opt_in" != "true" ]]; then
  emit "skip" "$(jq -nc '{reason:"behavioral_test not opted in for this entry"}')"
  exit 0
fi

if [[ "${CAIDO_BINARY_AVAILABLE:-false}" != "true" ]]; then
  emit "skip" "$(jq -nc '{reason:"CAIDO_BINARY_AVAILABLE != true; harness scaffold only — see roadmap feature-13"}')"
  exit 0
fi

# === REAL HARNESS LOGIC GOES HERE ===
# Pseudocode for what the real implementation should do once a Caido binary
# is available. None of this currently runs.
#
# 1. Stage the plugin tree (CACHED_REPO_DIR) into Caido's plugin directory.
# 2. Start a headless Caido instance with --disable-network.
# 3. Wait for ready signal (timeout 30s).
# 4. Assert the plugin's manifest reads cleanly (caido CLI: `caido plugin info`).
# 5. Trigger one no-op interaction (e.g. open the plugin's panel via UI bus).
# 6. Capture stdout/stderr/exitcode of the Caido process.
# 7. Outcome:
#      - Caido exited cleanly with plugin loaded     => status=pass
#      - Plugin loaded but threw on UI interaction   => status=warn
#      - Plugin failed to load                       => status=fail (still
#        non-blocking; the SAST + signature gates are the merge-blockers,
#        not this one)
#
# Output: caido-load-$ENTRY_NAME.json with the captured logs and outcome,
# uploaded as a workflow artifact alongside SBOM/SAST/CVE.

emit "fail" "$(jq -nc '{error:"harness body not implemented yet — see scripts/intake/caido-load-test.sh comment block"}')"
exit 0
