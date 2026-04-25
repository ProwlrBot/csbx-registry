#!/usr/bin/env bash
# Persist generated SBOM/SAST artifacts to the orphan `audit-archive` branch.
#
# Layout under audit-archive:
#   <section>/<name>/<release>/sbom.cdx.json
#   <section>/<name>/<release>/sast.json
#   <section>/<name>/<release>/manifest.json
#
# This is the durable home for attestation artifacts. raw.githubusercontent.com
# URLs into this branch are stable beyond the 90-day workflow-artifact lifetime
# and can be linked from registry.yaml entries' `attestations` block.
#
# Inputs (env):
#   ENTRY_NAME     registry key (e.g. "myplugin")
#   ENTRY_SECTION  one of pdtm_tools | plugins | caido_plugins
#   ENTRY_JSON     entry as JSON (jq-readable)
#   GH_TOKEN       GitHub PAT or workflow token with contents: write
#
# Reads from `attest-out/`:
#   sbom-<name>.cdx.json
#   sast-<name>.json (may be missing for non-caido types — that's fine)
#
# Idempotent: if the same content already exists at the target path,
# the commit is a no-op.
set -euo pipefail

: "${ENTRY_NAME:?}"
: "${ENTRY_SECTION:?}"
: "${ENTRY_JSON:?}"

release=$(jq -r '.release // "HEAD"' <<<"$ENTRY_JSON")
repo=$(jq -r '.repo' <<<"$ENTRY_JSON")
type=$(jq -r '.type // "unknown"' <<<"$ENTRY_JSON")

target_dir="$ENTRY_SECTION/$ENTRY_NAME/$release"
sbom_src="attest-out/sbom-$ENTRY_NAME.cdx.json"
sast_src="attest-out/sast-$ENTRY_NAME.json"

if [[ ! -f "$sbom_src" ]]; then
  echo "[-] persist: SBOM $sbom_src not found; skipping" >&2
  exit 1
fi

# Configure git identity up-front. Both the orphan-branch bootstrap and the
# attestation commit use it; the GH Actions runner doesn't have one by default.
# Use --global so the worktree (a separate working copy with its own .git
# index) inherits it without re-configuring.
git config --global user.name 'github-actions[bot]'
git config --global user.email '41898282+github-actions[bot]@users.noreply.github.com'
git config --global --add safe.directory "$GITHUB_WORKSPACE"

# Use a worktree pointed at the audit-archive branch so we don't disturb the
# main checkout. Initialise the orphan branch on first use.
worktree=$(mktemp -d)
trap 'rm -rf "$worktree"' EXIT

git fetch origin audit-archive 2>/dev/null || true
if git show-ref --verify --quiet refs/remotes/origin/audit-archive; then
  git worktree add -B audit-archive "$worktree" origin/audit-archive
else
  # First run: create the orphan branch with a README seed
  git worktree add --detach "$worktree" HEAD
  pushd "$worktree" >/dev/null
  git checkout --orphan audit-archive
  git rm -rf . >/dev/null 2>&1 || true
  cat > README.md <<'README'
# audit-archive

This orphan branch is the durable home for SBOM and SAST artifacts generated
by the intake workflow. Layout:

```
<section>/<entry-name>/<release>/
  sbom.cdx.json
  sast.json     (caido_plugins only; informational for other types)
  manifest.json
```

Each `manifest.json` records the upstream repo, release tag, intake commit
SHA, and timestamps for provenance. Files are committed by the
`Persist Attestations` workflow on every push to `main` that touches
`registry.yaml`.

This branch is **not** human-edited. Auto-commits only.
README
  git add README.md
  git commit -m "chore(audit-archive): initialise orphan branch"
  popd >/dev/null
fi

cd "$worktree"
mkdir -p "$target_dir"
cp -f "$GITHUB_WORKSPACE/$sbom_src" "$target_dir/sbom.cdx.json"
if [[ -f "$GITHUB_WORKSPACE/$sast_src" ]]; then
  cp -f "$GITHUB_WORKSPACE/$sast_src" "$target_dir/sast.json"
fi

# Write a manifest with provenance fields
cat > "$target_dir/manifest.json" <<MANIFEST
{
  "name": "$ENTRY_NAME",
  "section": "$ENTRY_SECTION",
  "type": "$type",
  "repo": "$repo",
  "release": "$release",
  "intake_sha": "${GITHUB_SHA:-unknown}",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "workflow_run": "${GITHUB_RUN_ID:-unknown}"
}
MANIFEST

# Idempotent commit
git add "$target_dir"
if git diff --cached --quiet; then
  echo "[+] persist: $target_dir unchanged; skipping commit"
  exit 0
fi
git commit -m "audit($ENTRY_SECTION/$ENTRY_NAME): persist $release attestations"
git push origin audit-archive
echo "[+] persist: pushed $target_dir"
