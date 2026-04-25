#!/usr/bin/env bash
# Verify that an entry's `repo` URL points at a public, non-archived GitHub
# repository, and (for caido-plugin) that the declared release tag exists.
#
# Inputs (env):
#   ENTRY_NAME  — registry key
#   ENTRY_JSON  — entry as JSON string (jq-readable)
#
# Output (stdout): single JSON line {"check":"repo","status":"pass|fail","details":{...},"blocking":true}
# Logs (stderr): human-readable
# Exits: 0 pass, 1 fail
set -euo pipefail

emit() {
  local status="$1" details="$2"
  printf '{"check":"repo","status":"%s","details":%s,"blocking":true}\n' \
    "$status" "$details"
}

fail() {
  local msg="$1"
  printf '[-] repo: %s\n' "$msg" >&2
  emit "fail" "$(jq -nc --arg m "$msg" '{error:$m}')"
  exit 1
}

: "${ENTRY_NAME:?ENTRY_NAME required}"
: "${ENTRY_JSON:?ENTRY_JSON required}"

repo=$(jq -r '.repo' <<<"$ENTRY_JSON")
type=$(jq -r '.type' <<<"$ENTRY_JSON")
release=$(jq -r '.release // empty' <<<"$ENTRY_JSON")

if [[ -z "$repo" || "$repo" == "null" ]]; then
  fail "missing repo URL for $ENTRY_NAME"
fi

# Extract owner/name from URL
slug=$(printf '%s' "$repo" | sed -E 's|^https://github\.com/([^/]+/[^/]+)/?$|\1|')
if [[ "$slug" == "$repo" ]]; then
  fail "repo URL did not parse: $repo"
fi

# Use the GitHub API; honor GITHUB_TOKEN if present (workflow provides it)
auth_args=()
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  auth_args=(-H "Authorization: Bearer $GITHUB_TOKEN")
fi

api="https://api.github.com/repos/$slug"
http_code=$(curl -s -o /tmp/intake-repo.json -w '%{http_code}' \
  -H 'Accept: application/vnd.github+json' \
  "${auth_args[@]}" \
  "$api" || true)

if [[ "$http_code" != "200" ]]; then
  fail "GitHub API returned $http_code for $slug"
fi

archived=$(jq -r '.archived' /tmp/intake-repo.json)
private=$(jq -r '.private' /tmp/intake-repo.json)

if [[ "$archived" == "true" ]]; then
  fail "repo $slug is archived"
fi
if [[ "$private" == "true" ]]; then
  fail "repo $slug is private"
fi

# Caido plugins must point at a real release tag
if [[ "$type" == "caido-plugin" ]]; then
  if [[ -z "$release" ]]; then
    fail "caido-plugin $ENTRY_NAME missing release field"
  fi
  rcode=$(curl -s -o /dev/null -w '%{http_code}' \
    -H 'Accept: application/vnd.github+json' \
    "${auth_args[@]}" \
    "https://api.github.com/repos/$slug/releases/tags/$release" || true)
  if [[ "$rcode" != "200" ]]; then
    fail "release tag $release not found in $slug (API returned $rcode)"
  fi
fi

printf '[+] repo: %s ok (release=%s)\n' "$slug" "${release:-n/a}" >&2
emit "pass" "$(jq -nc --arg s "$slug" --arg r "${release:-}" '{slug:$s,release:$r}')"
