# csbx-registry intake policy

This document is the source of truth for what the **Plugin Intake Check** workflow does on every pull request that touches `registry.yaml`. Read it before you open a PR, and read it again before you ship a `caido-plugin` entry.

## Goals

The registry sits between two failure modes:

- **Too permissive** — a malicious `caido-plugin` lands in the registry, ships into a hunter's Caido instance via `csbx install --caido`, and exfiltrates session cookies. Game over for the registry's reputation.
- **Too strict** — every plugin needs a multi-day signing dance to land, the registry stagnates, hunters keep installing plugins via `git clone | bash`, and we have failed our purpose.

The intake policy below picks a deliberate point on that spectrum:

- **Caido plugins** are executable, run inside a security tool, and have outsized blast radius. They get the strictest path: signature, SBOM, SAST blocking, schema, accessibility — all required.
- **All other plugin types** (tool, wordlist, theme, etc.) get a lighter path: schema, accessibility, SBOM, informational SAST. This matches the de facto policy for entries that landed before this workflow existed.

## What the workflow runs

The workflow lives at `.github/workflows/intake.yml`. It triggers on `pull_request` events that modify `registry.yaml`. It runs a set of jobs in parallel and posts a consolidated comment to the PR.

### Check 1 — Schema validation (required, all entries)

**Tool:** `scripts/intake/validate-schema.py` (Python + PyYAML)

**What it does:** Diffs the PR's `registry.yaml` against `main`, extracts added or modified entries, validates each against the schema. Errors:

- Missing required field (`repo`, `type`, `description`, `size`, `tags`)
- `type` not in the supported list
- `repo` not a well-formed `https://github.com/...` URL
- `tags` empty or non-list
- For `caido-plugin`: missing `release`, `manifest`, or `signature` block; `signature.method` not in `[cosign, minisign]`

**Failure ⇒ blocks merge.**

**Remediation:** Read the error message; it points at the exact field. Fix the entry and push.

### Check 2 — Repo accessibility (required, all entries)

**Tool:** `scripts/intake/check-repo.sh` (bash + curl)

**What it does:** `curl -sIL` the `repo` URL, follows redirects, checks for HTTP 200 and a non-archived state via the GitHub API. Also verifies that the declared `release` tag (if any) exists.

**Failure ⇒ blocks merge.** A registry pointing at dead links is worse than no registry.

**Remediation:** Make sure the repo is public and not archived. If you renamed the repo, update the URL.

### Check 3 — SBOM generation (required, all entries; blocking only on fatal errors)

**Tool:** [`syft`](https://github.com/anchore/syft) v1.x via `scripts/intake/generate-sbom.sh`

**What it does:** Clones the target repo at the declared `release` tag (or `HEAD` if none), runs `syft <dir> -o cyclonedx-json` to emit a CycloneDX SBOM. The SBOM is uploaded as a workflow artifact named `sbom-<plugin-name>.cdx.json`.

**Failure ⇒ blocks merge** only if `syft` fails to run (clone error, unsupported language). Empty SBOMs are allowed (e.g. wordlists have no dependencies). The SBOM is informational for review.

**Remediation:** If `syft` cannot infer your project's language, ensure your manifest files (`package.json`, `go.mod`, `pyproject.toml`, etc.) live at the repo root.

### Check 4 — SAST scan (required and blocking for caido-plugin; informational for others)

**Tool:** [`semgrep`](https://semgrep.dev) via `scripts/intake/run-sast.sh`

**What it does:** Clones the target repo, runs `semgrep --config=auto --severity=ERROR --severity=WARNING --metrics=off --json -o sast.json`. The configuration includes the public Semgrep auto-rules plus the `intake/semgrep-caido.yml` ruleset (Caido-specific patterns: hardcoded API keys, `eval` on attacker-controlled input, network calls outside declared scope, persistence to filesystem outside Caido's data dir).

**Severity threshold:**
- `caido-plugin`: any `ERROR` (HIGH/CRITICAL) finding **blocks merge**. `WARNING` findings are commented to the PR but do not block.
- Other types: all findings are commented but **none block**.

**Remediation:** Read the finding, fix the code, push, the workflow re-runs.

> **Policy decision flagged for review:** the threshold defaults to `ERROR`-blocks for `caido-plugin`. If this is too strict for the existing Caido ecosystem (where common patterns trip ERROR-level rules), drop to "block on a curated subset only." See [scripts/intake/run-sast.sh](../scripts/intake/run-sast.sh) — search for `BLOCK_LEVEL` to change.

### Check 5 — Signature verification (required for caido-plugin, skipped for others)

**Tool:** [`cosign`](https://github.com/sigstore/cosign) v2.x via `scripts/intake/verify-signature.sh`

**What it does:** For each `caido-plugin` entry, downloads the release asset for the declared `release` tag, looks up the cosign signature and certificate, and runs:

```bash
cosign verify-blob \
  --certificate-identity "<entry.signature.identity>" \
  --certificate-oidc-issuer "<entry.signature.issuer>" \
  --signature <release-asset>.sig \
  --certificate <release-asset>.pem \
  <release-asset>
```

This is **keyless** verification — no shared keypair to leak. The plugin's release workflow signs with the GitHub Actions OIDC identity at release time; we verify against the same identity at intake time.

**Failure ⇒ blocks merge** for `caido-plugin` entries. **Skipped** entirely for non-Caido entries.

**Remediation for plugin authors:** Wire keyless cosign signing into your release workflow. A minimal example:

```yaml
# .github/workflows/release.yml
permissions:
  contents: write
  id-token: write    # required for keyless cosign

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build artifact
        run: ./scripts/build.sh
      - uses: sigstore/cosign-installer@v3
      - name: Sign artifact
        run: |
          cosign sign-blob --yes \
            --output-signature dist/plugin.zip.sig \
            --output-certificate dist/plugin.zip.pem \
            dist/plugin.zip
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/plugin.zip
            dist/plugin.zip.sig
            dist/plugin.zip.pem
```

Then in your registry entry:

```yaml
signature:
  method: cosign
  issuer: https://token.actions.githubusercontent.com
  identity: https://github.com/<you>/<repo>/.github/workflows/release.yml@refs/tags/<tag>
```

If you genuinely cannot use cosign (e.g. self-hosted runner with no OIDC), use `method: minisign` and pin a public key. Maintainers reserve the right to decline minisign entries that look like an attempt to evade keyless attestation.

## What is *not* checked

Every check has a cost; we deliberately stop short of:

- **Sandbox execution.** We do not run the plugin's install hook in a VM. Hooks are reviewed manually by maintainers — and they are short. If a hook gets longer than 10 lines, that is a smell.
- **Behavioral fuzzing.** No live network requests, no Caido instance spun up to load the plugin. SAST + manual review is the substitute.
- **Dependency vulnerability scanning.** The SBOM is generated and stored; users can run `grype` against it themselves. The workflow does not gate merges on CVE counts because CVE noise is high and most CVEs are not exploitable in plugin code.

If you think one of these should be added, open an issue. We will weigh added security against added friction.

## Maintainer override

A maintainer can merge a PR with a failed required check **only if**:

1. The failure was a verifiable infrastructure issue (e.g. `syft` server 5xx) — re-run the workflow first; only override if it persists.
2. The override is documented in a PR review comment with the reason.
3. The maintainer has not authored the PR (no self-merging with a forced override).

Override is a last resort. The default is "fix the issue, push, merge."

## Versioning this policy

Material changes to this policy (new required check, raised threshold, removed check) ship as a PR that:

1. Updates this document
2. Updates the workflow and scripts in lockstep
3. Adds a fixture demonstrating the new behavior
4. Bumps the `policy_version` field in `registry.yaml` (top of file)

Authors of in-flight PRs are notified by a comment on their PR if a policy change would affect their entry.

---

**Last reviewed:** 2026-04-25
