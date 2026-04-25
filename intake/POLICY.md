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

#### Minisign — accepted-but-discouraged path

For `method: minisign`, the entry must declare `signature.public_key`. The validator (`scripts/intake/validate-schema.py`) enforces presence; the runtime path in `scripts/intake/verify-signature.sh` resolves the key as one of:

1. An inline base64 minisign public-key string (recommended — the registry entry is the trust root, no extra fetch).
2. An `https://` URL pointing at the public key file.
3. A path inside the repo (rarely useful in CI; documented for completeness).

The release artifact must include a detached `.minisig` next to the primary asset. The runtime invokes `minisign -V -p <key> -m <artifact> -x <artifact>.minisig`.

```yaml
signature:
  method: minisign
  public_key: "RWQfaLPThpUXaqEf+34S2QBaW9R8tPlQk0L1qJqW9Q4dB5e0hEMx2bHE"
```

A tampered artifact or wrong-key fixture must produce a non-zero exit from `verify-signature.sh` — this is exercised by fixtures under `tests/fixtures/`.

## Non-goals

These are deliberate, versioned decisions — not oversights. Each is dated and tied to the `policy_version` so a future revisit can read the rationale before relitigating it.

### NG-1 · Sandbox execution of install hooks

> **Decision:** csbx-registry does NOT execute plugin install hooks in a sandbox or VM as part of intake.
> **Decided under policy_version:** `2026-04-25`

**Rationale.** Install hooks run on the user's machine via the [csbx CLI](https://github.com/kdairatchi/cybersandbox), which is out of scope for the registry. Sandboxing a hook in CI would not protect the user — it would only verify "this hook does X under our sandbox conditions," which the hook author can game and which says nothing about the hook's behavior on a real workstation. The substitutes are:

1. **Manual review.** Hooks longer than 10 lines are a smell and get rejected.
2. **SAST.** `intake/semgrep-caido.yml` flags shell-injection sinks, hardcoded credentials, and `eval`-on-untrusted-input.
3. **Signature verification.** For `caido-plugin`, the hook ships in a cosign-signed release; an attacker would have to compromise the plugin author's GitHub OIDC identity to swap the hook silently.

**Cost of changing this.** Sandbox tooling at intake time would require a per-plugin runner image, network egress controls, and a deterministic execution environment for every supported install backend (`go install`, `npm`, `git clone`, `pip`, etc.). The complexity is high; the benefit (catching a hostile hook in CI rather than at install time) is bounded by the user's local environment differing from CI anyway.

**If you want to revisit this**, open an issue with: a concrete attack a sandbox would catch that the three substitutes above would miss, and a sketch of the per-backend runner setup. Without both, the issue will be closed as "see NG-1."

### NG-2 · Mirroring or CDN of upstream artifacts

> **Decision:** csbx-registry does NOT mirror release tarballs, host a CDN, or stage upstream artifacts. The registry is a **manifest pointing at upstream GitHub repos**, so upstream availability == registry availability.
> **Decided under policy_version:** `2026-04-25`

**Rationale.** A mirror would require:

- Storage and bandwidth scaling with the catalog (currently ~5GB across SecLists, assetnote-wordlists, etc.; growing).
- A re-publish pipeline keyed on upstream releases.
- A trust story for "the mirror is the same as upstream" — adding cosign re-signing, hash audits, or both.
- An incident response process for "the mirror was tampered with" that does not exist for the manifest-only model.

We have three contributors. The registry's value is curation + intake gating, not artifact hosting. Spending maintainer time on a mirror trades that core value for redundancy that GitHub already provides (and that an air-gap user can build for themselves with `tools/prefetch.sh` once shipped).

**What we recommend instead — user-side artifact pinning.** Users who need availability guarantees beyond GitHub:

1. Clone csbx-registry locally; treat your clone as the manifest of record.
2. For each entry you depend on, download the upstream release tarball at a pinned tag.
3. Verify the cosign signature (for `caido-plugin`) or pin the SHA-256 (for everything else) in your own bookkeeping.
4. Cache the tarball + signature + verification log in a location you control (NAS, S3, USB, whatever your engagement allows).
5. Resolve installs from your local cache.

This gives you the same availability story as a mirror without making the registry responsible for it. See `OFFLINE.md` (when shipped) for a worked example.

**If you want to revisit this**, open an issue with: the failure mode you have hit that user-side pinning does not address, and a contributor who is committing to operating the mirror. Without both, the issue will be closed as "see NG-2."

### NG-3 · Behavioral fuzzing of plugins at intake

> **Decision:** csbx-registry does NOT run plugins against synthetic traffic, fuzz inputs, or otherwise exercise behavior at intake time.
> **Status:** active — behavioral live-load smoke testing scaffolded (off by default, never blocking)
> **Decided under policy_version:** `2026-04-25`

The substitutes are SAST and manual review.

**What we DO offer (scaffold):** caido-plugin entries can opt in to a behavioral live-load test by setting `behavioral_test: true` on the entry. The intake job at `scripts/intake/caido-load-test.sh` will, when a Caido binary is available on the runner (gated on `vars.CAIDO_BINARY_AVAILABLE == 'true'`), stage the plugin into a headless Caido instance and assert it loads and accepts a no-op UI interaction without crashing. See the script for the documented harness contract.

**Status as of policy_version 2026-04-25:** the harness body is not implemented because no CI-friendly Caido binary is currently distributed. The job slot exists so the runtime can be wired in later without a workflow refactor. Outcomes from the scaffold are always emitted as `skip` until the binary is available; outcomes from the eventual real harness will be informational regardless of result.

### NG-4 · Blocking on dependency CVEs

> **Decision:** csbx-registry does NOT block merge on CVE counts in the SBOM.
> **Status:** active — informational signal ENABLED (non-blocking)
> **Decided under policy_version:** `2026-04-25`

Per CVE noise being high (and most CVEs in plugin dependencies not being exploitable in the plugin's actual code path), gating on CVE count would generate review fatigue without proportional security gain.

**What we DO offer:** an opt-in [grype](https://github.com/anchore/grype) scan runs on every PR (the `CVE (info)` job in `.github/workflows/intake.yml`). It scans the just-generated SBOM and posts a summary count by severity to the PR comment. The result is **never blocking**; maintainers may use the signal as input to their review judgment but are explicitly free to merge over CVE findings. The CVE artifact is uploaded alongside the SBOM and SAST artifacts and persisted to the `audit-archive` branch on push to main.

This distinguishes "informational CVE signal" (now offered) from "CVE gating" (still a non-goal).

---

If you think one of these should be added, open an issue with the format above (concrete failure mode + concrete owner). We will weigh added security against added friction.

## Persistent attestation archive

SBOM and SAST artifacts are written to two places:

1. **GitHub Actions workflow artifacts** — created by the PR intake workflow, expire after 90 days. Useful for the PR's review window only.
2. **The orphan [`audit-archive`](https://github.com/ProwlrBot/csbx-registry/tree/audit-archive) branch** — created by the [`Persist Attestations`](../.github/workflows/persist-attestations.yml) workflow on every push to `main`. **Durable beyond 90 days.**

Layout under `audit-archive`:

```
<section>/<entry-name>/<release>/
  sbom.cdx.json
  sast.json         (caido_plugins only; informational for other types)
  manifest.json     (provenance: upstream repo, release tag, intake SHA, timestamps)
```

Each registry entry can declare an `attestations` block with stable URLs into this branch:

```yaml
my-caido-plugin:
  # ... other fields ...
  attestations:
    sbom_url: https://raw.githubusercontent.com/ProwlrBot/csbx-registry/audit-archive/caido_plugins/my-caido-plugin/v1.2.0/sbom.cdx.json
    sast_url: https://raw.githubusercontent.com/ProwlrBot/csbx-registry/audit-archive/caido_plugins/my-caido-plugin/v1.2.0/sast.json
```

The contract schema (`intake/registry-contract.schema.json`) accepts the `attestations` block; INDEX.md surfaces these URLs as badges. Adding the block is optional — the artifacts exist on the orphan branch regardless — but linking them from the entry makes them discoverable.

## Scheduled stale-entry detection

A separate workflow at [`.github/workflows/stale-check.yml`](../.github/workflows/stale-check.yml) runs weekly (Mondays 06:00 UTC) and exercises a lightweight version of [Check 2 — Repo accessibility](#check-2--repo-accessibility-required-all-entries) against every entry in `registry.yaml`.

When an entry's upstream becomes archived, deleted (404), made private, or — for `caido-plugin` entries — has its declared release tag removed, the workflow auto-opens an issue with the `stale-entry` label. Issues are deduplicated on `(entry, reason)`; a re-run that sees the same condition appends a comment to the existing issue rather than opening a new one.

A maintainer is expected to:

1. Confirm the finding by visiting the upstream repo manually.
2. Open a removal PR if the entry is genuinely stale, or close the issue with a comment if the condition was transient.
3. Re-running the workflow under `workflow_dispatch` is supported and useful when investigating intermittent failures.

The workflow is operationally independent from the PR-time intake (different trigger, different concurrency group, `issues: write` permission instead of `pull-requests: write`). A failed scan does not block PR merges; it only signals catalog rot.

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
4. Updates the `policy_version` field in `registry.yaml` (top of file) to the current ISO-8601 date

The `policy_version` field is machine-enforced: the `manifest` job in `.github/workflows/intake.yml` runs `scripts/intake/validate-manifest.py` on every PR that touches `registry.yaml`. It rejects any PR where `policy_version` is missing or older than the value on `main`. You cannot merge a policy-touching PR without bumping this field.

Schema-version (`registry.yaml`'s top-level `version` field) bumps follow a separate, more involved process — see [`MIGRATIONS.md`](../MIGRATIONS.md). The validator's `SUPPORTED_VERSIONS` and `DEPRECATED_VERSIONS` sets gate which versions are accepted at intake; mechanical migrations live in `scripts/intake/migrate-registry.py`.

Authors of in-flight PRs are notified by a comment on their PR if a policy change would affect their entry.

---

**Last reviewed:** 2026-04-25
