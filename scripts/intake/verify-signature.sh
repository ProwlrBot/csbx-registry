#!/usr/bin/env bash
# Verify the cosign keyless signature on the release artifact for a caido-plugin.
#
# Inputs (env):
#   ENTRY_NAME, ENTRY_JSON
#   SIG_OUT_DIR (default: ./sig-out)
#
# Output (stdout): JSON line
# Exits:
#   0 — pass (or skip for non-caido-plugin)
#   1 — fail
set -euo pipefail

SIG_OUT_DIR="${SIG_OUT_DIR:-./sig-out}"
mkdir -p "$SIG_OUT_DIR"

emit() {
  local status="$1" details="$2" blocking="${3:-true}"
  printf '{"check":"signature","status":"%s","details":%s,"blocking":%s}\n' \
    "$status" "$details" "$blocking"
}

: "${ENTRY_NAME:?}"
: "${ENTRY_JSON:?}"

type=$(jq -r '.type' <<<"$ENTRY_JSON")

if [[ "$type" != "caido-plugin" ]]; then
  printf '[*] signature: skipped (type=%s)\n' "$type" >&2
  emit "skip" "$(jq -nc --arg t "$type" '{reason:"non-caido type",type:$t}')" "false"
  exit 0
fi

if ! command -v cosign >/dev/null 2>&1; then
  printf '[-] signature: cosign not installed\n' >&2
  emit "fail" "$(jq -nc '{error:"cosign not installed"}')" "true"
  exit 1
fi

repo=$(jq -r '.repo' <<<"$ENTRY_JSON")
release=$(jq -r '.release' <<<"$ENTRY_JSON")
manifest=$(jq -r '.manifest // "caido.json"' <<<"$ENTRY_JSON")
sig_method=$(jq -r '.signature.method' <<<"$ENTRY_JSON")
issuer=$(jq -r '.signature.issuer' <<<"$ENTRY_JSON")
identity=$(jq -r '.signature.identity' <<<"$ENTRY_JSON")
slug=$(printf '%s' "$repo" | sed -E 's|^https://github\.com/([^/]+/[^/]+)/?$|\1|')

if [[ "$sig_method" != "cosign" ]]; then
  printf '[!] signature: method=%s (skipping cosign verification)\n' "$sig_method" >&2
  emit "skip" "$(jq -nc --arg m "$sig_method" '{reason:"non-cosign method",method:$m}')" "true"
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Pull the assets list for the release
auth_args=()
[[ -n "${GITHUB_TOKEN:-}" ]] && auth_args=(-H "Authorization: Bearer $GITHUB_TOKEN")

api="https://api.github.com/repos/$slug/releases/tags/$release"
if ! curl -s -H 'Accept: application/vnd.github+json' "${auth_args[@]}" "$api" \
  >"$work/release.json"; then
  emit "fail" "$(jq -nc '{error:"release API fetch failed"}')" "true"
  exit 1
fi

# Find the primary asset (anything non-.sig, non-.pem)
primary=$(jq -r '.assets[] | select((.name|endswith(".sig"))|not)
  | select((.name|endswith(".pem"))|not) | .browser_download_url' \
  "$work/release.json" | head -n1)
sig=$(jq -r --arg m "$manifest" '.assets[]
  | select(.name|test(".sig$")) | .browser_download_url' \
  "$work/release.json" | head -n1)
cert=$(jq -r '.assets[]
  | select(.name|test(".pem$")) | .browser_download_url' \
  "$work/release.json" | head -n1)

if [[ -z "$primary" || -z "$sig" || -z "$cert" ]]; then
  emit "fail" "$(jq -nc \
    --arg p "$primary" --arg s "$sig" --arg c "$cert" \
    '{error:"missing assets",primary:$p,signature:$s,certificate:$c}')" "true"
  exit 1
fi

curl -sL -o "$work/artifact" "$primary"
curl -sL -o "$work/artifact.sig" "$sig"
curl -sL -o "$work/artifact.pem" "$cert"

if cosign verify-blob \
  --certificate-identity "$identity" \
  --certificate-oidc-issuer "$issuer" \
  --signature "$work/artifact.sig" \
  --certificate "$work/artifact.pem" \
  "$work/artifact" >"$SIG_OUT_DIR/cosign-$ENTRY_NAME.log" 2>&1; then
  printf '[+] signature: %s verified\n' "$ENTRY_NAME" >&2
  emit "pass" "$(jq -nc \
    --arg i "$identity" --arg iss "$issuer" \
    '{identity:$i, issuer:$iss}')" "true"
  exit 0
fi

cat "$SIG_OUT_DIR/cosign-$ENTRY_NAME.log" >&2
emit "fail" "$(jq -nc \
  --arg i "$identity" --arg iss "$issuer" \
  '{error:"cosign verify-blob failed",identity:$i,issuer:$iss}')" "true"
exit 1
