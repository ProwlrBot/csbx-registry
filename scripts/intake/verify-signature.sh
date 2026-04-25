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

repo=$(jq -r '.repo' <<<"$ENTRY_JSON")
release=$(jq -r '.release' <<<"$ENTRY_JSON")
manifest=$(jq -r '.manifest // "caido.json"' <<<"$ENTRY_JSON")
sig_method=$(jq -r '.signature.method' <<<"$ENTRY_JSON")
slug=$(printf '%s' "$repo" | sed -E 's|^https://github\.com/([^/]+/[^/]+)/?$|\1|')

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Pull the assets list for the release (shared between cosign and minisign paths)
auth_args=()
[[ -n "${GITHUB_TOKEN:-}" ]] && auth_args=(-H "Authorization: Bearer $GITHUB_TOKEN")

api="https://api.github.com/repos/$slug/releases/tags/$release"
if ! curl -s -H 'Accept: application/vnd.github+json' "${auth_args[@]}" "$api" \
  >"$work/release.json"; then
  emit "fail" "$(jq -nc '{error:"release API fetch failed"}')" "true"
  exit 1
fi

verify_cosign() {
  local issuer identity
  issuer=$(jq -r '.signature.issuer' <<<"$ENTRY_JSON")
  identity=$(jq -r '.signature.identity' <<<"$ENTRY_JSON")

  local primary sig cert
  primary=$(jq -r '.assets[] | select((.name|endswith(".sig"))|not)
    | select((.name|endswith(".pem"))|not) | .browser_download_url' \
    "$work/release.json" | head -n1)
  sig=$(jq -r '.assets[] | select(.name|test(".sig$")) | .browser_download_url' \
    "$work/release.json" | head -n1)
  cert=$(jq -r '.assets[] | select(.name|test(".pem$")) | .browser_download_url' \
    "$work/release.json" | head -n1)

  if [[ -z "$primary" || -z "$sig" || -z "$cert" ]]; then
    emit "fail" "$(jq -nc \
      --arg p "$primary" --arg s "$sig" --arg c "$cert" \
      '{error:"cosign: missing assets (need primary + .sig + .pem)",primary:$p,signature:$s,certificate:$c}')" "true"
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
    printf '[+] signature: %s verified (cosign)\n' "$ENTRY_NAME" >&2
    emit "pass" "$(jq -nc --arg i "$identity" --arg iss "$issuer" \
      '{method:"cosign",identity:$i,issuer:$iss}')" "true"
    return 0
  fi

  cat "$SIG_OUT_DIR/cosign-$ENTRY_NAME.log" >&2
  emit "fail" "$(jq -nc --arg i "$identity" --arg iss "$issuer" \
    '{error:"cosign verify-blob failed",identity:$i,issuer:$iss}')" "true"
  exit 1
}

verify_minisign() {
  local public_key
  public_key=$(jq -r '.signature.public_key' <<<"$ENTRY_JSON")

  if [[ -z "$public_key" || "$public_key" == "null" ]]; then
    emit "fail" "$(jq -nc '{error:"minisign: signature.public_key not set"}')" "true"
    exit 1
  fi

  if ! command -v minisign >/dev/null 2>&1; then
    emit "fail" "$(jq -nc '{error:"minisign not installed"}')" "true"
    exit 1
  fi

  # Resolve public_key: either an inline base64 key, an https URL, or a path
  # inside the release artifacts. Inline is the safest because the registry
  # entry is the trust root.
  local key_file="$work/minisign.pub"
  if [[ "$public_key" =~ ^https?:// ]]; then
    curl -sL -o "$key_file" "$public_key"
  elif [[ -f "$public_key" ]]; then
    cp "$public_key" "$key_file"
  else
    # Treat as inline minisign public key string
    printf '%s\n' "$public_key" >"$key_file"
  fi

  # Pick the primary artifact (non-.minisig) and its detached .minisig counterpart.
  local primary sig
  primary=$(jq -r '.assets[] | select((.name|endswith(".minisig"))|not) | .browser_download_url' \
    "$work/release.json" | head -n1)
  sig=$(jq -r '.assets[] | select(.name|endswith(".minisig")) | .browser_download_url' \
    "$work/release.json" | head -n1)

  if [[ -z "$primary" || -z "$sig" ]]; then
    emit "fail" "$(jq -nc --arg p "$primary" --arg s "$sig" \
      '{error:"minisign: missing assets (need primary + .minisig)",primary:$p,signature:$s}')" "true"
    exit 1
  fi

  curl -sL -o "$work/artifact" "$primary"
  curl -sL -o "$work/artifact.minisig" "$sig"

  if minisign -V -p "$key_file" -m "$work/artifact" -x "$work/artifact.minisig" \
    >"$SIG_OUT_DIR/minisign-$ENTRY_NAME.log" 2>&1; then
    printf '[+] signature: %s verified (minisign)\n' "$ENTRY_NAME" >&2
    emit "pass" "$(jq -nc --arg pk "$public_key" \
      '{method:"minisign",public_key:$pk}')" "true"
    return 0
  fi

  cat "$SIG_OUT_DIR/minisign-$ENTRY_NAME.log" >&2
  emit "fail" "$(jq -nc --arg pk "$public_key" \
    '{error:"minisign verify failed",public_key:$pk}')" "true"
  exit 1
}

case "$sig_method" in
  cosign)
    if ! command -v cosign >/dev/null 2>&1; then
      printf '[-] signature: cosign not installed\n' >&2
      emit "fail" "$(jq -nc '{error:"cosign not installed"}')" "true"
      exit 1
    fi
    verify_cosign
    ;;
  minisign)
    verify_minisign
    ;;
  *)
    emit "fail" "$(jq -nc --arg m "$sig_method" \
      '{error:"unsupported signature method",method:$m}')" "true"
    exit 1
    ;;
esac
