#!/usr/bin/env bash
# SAST scan via semgrep. Blocking for caido-plugin, informational otherwise.
#
# Inputs (env):
#   ENTRY_NAME, ENTRY_JSON
#   SAST_OUT_DIR (default: ./sast-out)
#   BLOCK_LEVEL  (default: ERROR — change to a tighter set if needed)
#
# Output (stdout): JSON line
# Exits:
#   0 — no blocking findings
#   1 — blocking findings present (only for caido-plugin)
set -euo pipefail

SAST_OUT_DIR="${SAST_OUT_DIR:-./sast-out}"
BLOCK_LEVEL="${BLOCK_LEVEL:-ERROR}"
mkdir -p "$SAST_OUT_DIR"

emit() {
  local status="$1" details="$2" blocking="${3:-true}"
  printf '{"check":"sast","status":"%s","details":%s,"blocking":%s}\n' \
    "$status" "$details" "$blocking"
}

: "${ENTRY_NAME:?}"
: "${ENTRY_JSON:?}"

repo=$(jq -r '.repo' <<<"$ENTRY_JSON")
release=$(jq -r '.release // "HEAD"' <<<"$ENTRY_JSON")
type=$(jq -r '.type' <<<"$ENTRY_JSON")

if ! command -v semgrep >/dev/null 2>&1; then
  printf '[-] sast: semgrep not installed\n' >&2
  emit "fail" "$(jq -nc '{error:"semgrep not installed"}')" "true"
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

clone_args=(--depth 1)
[[ "$release" != "HEAD" ]] && clone_args+=(--branch "$release")
git clone "${clone_args[@]}" "$repo" "$work/src" >/dev/null 2>&1 || {
  printf '[-] sast: clone failed\n' >&2
  emit "fail" "$(jq -nc --arg r "$repo" '{error:"clone failed",repo:$r}')" "true"
  exit 1
}

out="$SAST_OUT_DIR/sast-$ENTRY_NAME.json"
caido_rules="$(dirname "$0")/../../intake/semgrep-caido.yml"

# Build config args; auto rules + Caido-specific if file exists
configs=(--config=auto)
if [[ -f "$caido_rules" ]]; then
  configs+=("--config=$caido_rules")
fi

semgrep "${configs[@]}" \
  --metrics=off \
  --json -o "$out" \
  --no-error \
  "$work/src" >/dev/null 2>/tmp/semgrep.err || true

if [[ ! -s "$out" ]]; then
  printf '[-] sast: semgrep produced no output\n' >&2
  cat /tmp/semgrep.err >&2 || true
  emit "fail" "$(jq -nc '{error:"semgrep produced no output"}')" "true"
  exit 1
fi

errors=$(jq '[.results[] | select(.extra.severity == "ERROR")] | length' "$out")
warnings=$(jq '[.results[] | select(.extra.severity == "WARNING")] | length' "$out")

is_blocking="false"
status="pass"
if [[ "$type" == "caido-plugin" ]]; then
  is_blocking="true"
  if [[ "$errors" -gt 0 ]]; then
    status="fail"
  fi
fi

details=$(jq -nc \
  --arg p "$out" \
  --argjson e "$errors" \
  --argjson w "$warnings" \
  --arg t "$type" \
  --arg b "$BLOCK_LEVEL" \
  '{path:$p, error_findings:$e, warning_findings:$w, type:$t, block_level:$b}')

printf '[+] sast: %s -> errors=%s warnings=%s (blocking=%s)\n' \
  "$ENTRY_NAME" "$errors" "$warnings" "$is_blocking" >&2

emit "$status" "$details" "$is_blocking"

if [[ "$status" == "fail" && "$is_blocking" == "true" ]]; then
  exit 1
fi
exit 0
