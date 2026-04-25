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

# Resolve forge metadata via the Python adapter (covers GitHub, GitLab, Codeberg)
forge_info=$(python3 "$(dirname "$0")/forge_adapter.py" info "$repo" 2>/dev/null || true)
if [[ -z "$forge_info" ]] || jq -e '.error' <<<"$forge_info" >/dev/null 2>&1; then
  fail "repo URL not supported by any forge adapter: $repo"
fi
forge=$(jq -r '.forge' <<<"$forge_info")
slug=$(jq -r '.slug' <<<"$forge_info")
api=$(jq -r '.api_repo_url' <<<"$forge_info")

# Auth: GitHub uses Bearer token; GitLab uses PRIVATE-TOKEN; Codeberg accepts
# Bearer for the API. The workflow only injects GITHUB_TOKEN today; other forges
# are public-API friendly so the absence of a token is acceptable for read.
auth_args=()
if [[ "$forge" == "github" && -n "${GITHUB_TOKEN:-}" ]]; then
  auth_args=(-H "Authorization: Bearer $GITHUB_TOKEN")
elif [[ "$forge" == "gitlab" && -n "${GITLAB_TOKEN:-}" ]]; then
  auth_args=(-H "PRIVATE-TOKEN: $GITLAB_TOKEN")
elif [[ "$forge" == "codeberg" && -n "${CODEBERG_TOKEN:-}" ]]; then
  auth_args=(-H "Authorization: token $CODEBERG_TOKEN")
fi

http_code=$(curl -s -o /tmp/intake-repo.json -w '%{http_code}' \
  -H 'Accept: application/json' \
  "${auth_args[@]}" \
  "$api" || true)

if [[ "$http_code" != "200" ]]; then
  fail "$forge API returned $http_code for $slug"
fi

archived=$(jq -r '.archived // false' /tmp/intake-repo.json)
# GitLab uses .visibility instead of .private
private=$(jq -r 'if has("visibility") then (.visibility == "private")
                 else (.private // false) end' /tmp/intake-repo.json)

if [[ "$archived" == "true" ]]; then
  fail "repo $slug ($forge) is archived"
fi
if [[ "$private" == "true" ]]; then
  fail "repo $slug ($forge) is private"
fi

# Caido plugins must point at a real release tag
release_json=""
if [[ "$type" == "caido-plugin" ]]; then
  if [[ -z "$release" ]]; then
    fail "caido-plugin $ENTRY_NAME missing release field"
  fi
  release_info=$(python3 "$(dirname "$0")/forge_adapter.py" release "$repo" "$release" 2>/dev/null || true)
  release_url=$(jq -r '.release_url // empty' <<<"$release_info")
  if [[ -z "$release_url" ]]; then
    fail "could not resolve release URL for $forge/$slug @ $release"
  fi
  release_json=$(mktemp)
  rcode=$(curl -s -o "$release_json" -w '%{http_code}' \
    -H 'Accept: application/json' \
    "${auth_args[@]}" \
    "$release_url" || true)
  if [[ "$rcode" != "200" ]]; then
    rm -f "$release_json"
    fail "release tag $release not found in $slug ($forge API returned $rcode)"
  fi
fi

# Per-platform asset coverage check (any entry can declare platforms;
# only meaningful when a release tag and asset list are available).
platforms=$(jq -r '.platforms[]? // empty' <<<"$ENTRY_JSON")
if [[ -n "$platforms" ]]; then
  if [[ -z "$release_json" ]]; then
    # Non-caido entry declared platforms — fetch the release JSON to check assets.
    if [[ -z "$release" ]]; then
      fail "entry $ENTRY_NAME declares platforms but has no release tag"
    fi
    release_json=$(mktemp)
    curl -s -H 'Accept: application/vnd.github+json' "${auth_args[@]}" \
      "https://api.github.com/repos/$slug/releases/tags/$release" >"$release_json" || true
  fi

  asset_names=$(jq -r '.assets[]?.name // empty' "$release_json" | tr 'A-Z' 'a-z')
  if [[ -z "$asset_names" ]]; then
    rm -f "$release_json"
    fail "release $release in $slug has no assets to satisfy declared platforms"
  fi

  missing=()
  while IFS= read -r platform; do
    [[ -z "$platform" ]] && continue
    os="${platform%-*}"
    arch="${platform#*-}"
    # Match if any asset name contains both os and arch (or the arch alias).
    found=""
    while IFS= read -r asset; do
      if [[ "$asset" == *"$os"* ]]; then
        if [[ "$arch" == "amd64" && ( "$asset" == *amd64* || "$asset" == *x86_64* || "$asset" == *x64* ) ]]; then
          found="$asset"; break
        elif [[ "$arch" == "arm64" && ( "$asset" == *arm64* || "$asset" == *aarch64* ) ]]; then
          found="$asset"; break
        fi
      fi
    done <<<"$asset_names"
    if [[ -z "$found" ]]; then
      missing+=("$platform")
    fi
  done <<<"$platforms"

  if [[ ${#missing[@]} -gt 0 ]]; then
    rm -f "$release_json"
    fail "release $release missing assets for: ${missing[*]}"
  fi
fi

[[ -n "$release_json" ]] && rm -f "$release_json"
printf '[+] repo: %s ok (release=%s)\n' "$slug" "${release:-n/a}" >&2
emit "pass" "$(jq -nc --arg s "$slug" --arg r "${release:-}" '{slug:$s,release:$r}')"
