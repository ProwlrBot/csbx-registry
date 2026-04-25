#!/usr/bin/env bash
# Generate a CycloneDX SBOM for the entry's repo at the declared release.
#
# Inputs (env):
#   ENTRY_NAME, ENTRY_JSON
#   SBOM_OUT_DIR (default: ./sbom-out)
#
# Output (stdout): JSON line
# Exits: 0 pass, 1 fail (only on infra failure — empty SBOM is allowed)
set -euo pipefail

SBOM_OUT_DIR="${SBOM_OUT_DIR:-./sbom-out}"
mkdir -p "$SBOM_OUT_DIR"

emit() {
  local status="$1" details="$2" blocking="${3:-true}"
  printf '{"check":"sbom","status":"%s","details":%s,"blocking":%s}\n' \
    "$status" "$details" "$blocking"
}

fail() {
  printf '[-] sbom: %s\n' "$1" >&2
  emit "fail" "$(jq -nc --arg m "$1" '{error:$m}')" "true"
  exit 1
}

: "${ENTRY_NAME:?}"
: "${ENTRY_JSON:?}"

repo=$(jq -r '.repo' <<<"$ENTRY_JSON")
release=$(jq -r '.release // "HEAD"' <<<"$ENTRY_JSON")
slug=$(printf '%s' "$repo" | sed -E 's|^https://github\.com/([^/]+/[^/]+)/?$|\1|')

if ! command -v syft >/dev/null 2>&1; then
  fail "syft not installed; cannot generate SBOM"
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Shallow clone, optionally at a tag
clone_args=(--depth 1)
if [[ "$release" != "HEAD" ]]; then
  clone_args+=(--branch "$release")
fi

if ! git clone "${clone_args[@]}" "$repo" "$work/src" >/dev/null 2>&1; then
  fail "git clone failed for $repo @ $release"
fi

out="$SBOM_OUT_DIR/sbom-$ENTRY_NAME.cdx.json"
if ! syft "$work/src" -o cyclonedx-json="$out" --quiet 2>/tmp/syft.err; then
  cat /tmp/syft.err >&2
  fail "syft failed for $ENTRY_NAME"
fi

components=$(jq -r '.components | length // 0' "$out")
printf '[+] sbom: %s -> %s components @ %s\n' "$ENTRY_NAME" "$components" "$out" >&2

emit "pass" "$(jq -nc \
  --arg p "$out" \
  --arg c "$components" \
  --arg r "$release" \
  '{path:$p, components:($c|tonumber), release:$r}')"
