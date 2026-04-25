# Contributing to csbx-registry

csbx-registry is the default plugin discovery layer for [CyberSandbox](https://github.com/kdairatchi/cybersandbox) and a community catalog for **Caido** plugins. Pull requests are welcome from any maintainer of a well-maintained plugin — you do not need to be a CyberBox author.

This document covers contribution mechanics. The intake security policy lives in [`intake/POLICY.md`](./intake/POLICY.md) — read it first if you are submitting a `caido-plugin` entry.

---

## Quick start

1. Fork this repo
2. Add your entry to `registry.yaml` under the appropriate section (alphabetical within type)
3. Open a PR; the **Plugin Intake Check** workflow runs automatically
4. Address any failed checks and push fixes; the workflow re-runs on each push
5. A maintainer reviews and merges once required checks are green

If your plugin lives in a public GitHub repo and ships a `csbx.yaml` (or, for Caido, a Caido manifest), you are 90% of the way there.

---

## Sections in `registry.yaml`

| Section | What goes here |
|---------|----------------|
| `pdtm_tools` | ProjectDiscovery tools installed via the Go toolchain |
| `plugins.<type>` | Wordlists, nuclei templates, configs, YARA, Sigma, threat-intel, themes |
| `caido_plugins` | Caido plugins (subject to the strict intake policy below) |

Pick the section that matches your `type` field. If your plugin spans types (e.g. a tool that ships a wordlist), pick the dominant function.

---

## Required fields

All entries:

```yaml
my-plugin:
  repo: https://github.com/user/repo   # public, accessible at PR time
  type: <one of the supported types>
  description: "One sentence, plain text"
  size: "10MB"                          # approximate, human-readable
  tags: [tag1, tag2]                    # at least one
```

`repo` may point at any of the **supported forges**: `github.com`, `gitlab.com`, `codeberg.org`. The intake workflow uses `scripts/intake/forge_adapter.py` to dispatch on the forge and call the right API. For non-GitHub forges, accessibility checks pass without any required token (public read API), but maintainers can configure `GITLAB_TOKEN` / `CODEBERG_TOKEN` repo secrets to raise rate limits — see [the workflow](./.github/workflows/intake.yml) for the env wiring. Other forges (bitbucket, sourcehut, self-hosted) are not currently supported; open an issue if you need one.

Caido plugins additionally:

```yaml
my-caido-plugin:
  repo: https://github.com/user/caido-plugin
  type: caido-plugin
  description: "What it does in Caido"
  size: "2MB"
  tags: [caido, http]
  release: v1.2.0                       # tag the intake workflow will pull
  manifest: caido.json                  # path inside the release artifact (default: caido.json)
  platforms:                            # OPTIONAL — declare install targets
    - linux-amd64
    - darwin-arm64
  signature:
    method: cosign                      # cosign | minisign (cosign preferred)
    issuer: https://token.actions.githubusercontent.com
    identity: https://github.com/user/caido-plugin/.github/workflows/release.yml@refs/tags/v1.2.0
```

**`platforms` (optional)** — declare which OS+arch combinations your release ships. Valid values: `linux-amd64`, `linux-arm64`, `darwin-amd64`, `darwin-arm64`, `windows-amd64`, `windows-arm64`. When set, intake asserts a matching asset exists in the GitHub release for each declared platform. Asset name match is case-insensitive substring on `<os>` plus `<arch>` (with `amd64`/`x86_64`/`x64` and `arm64`/`aarch64` treated as aliases). Omit if your plugin is platform-agnostic (e.g. pure JS).

The `signature` block is **required** for `caido-plugin` entries. See [intake/POLICY.md](./intake/POLICY.md) for how to wire keyless signing in your release workflow if you do not already.

---

## Intake checks (what runs on your PR)

The `Plugin Intake Check` workflow runs on every PR that touches `registry.yaml`:

| Check | Required? | Tool | What it does |
|-------|-----------|------|--------------|
| Schema validation | ✅ all entries | yq + Python | Confirms required fields, valid type, well-formed URLs |
| Repo accessibility | ✅ all entries | curl | Confirms `repo` URL returns 200 and is public |
| SBOM generation | ✅ all entries | [syft](https://github.com/anchore/syft) | Generates CycloneDX SBOM from the source tree; uploaded as a workflow artifact |
| SAST scan | ✅ caido-plugin, ⚠️ informational for others | [semgrep](https://semgrep.dev/) | Runs `--config=auto` plus a Caido-specific ruleset. **HIGH/CRITICAL findings block merge for `caido-plugin` entries.** |
| Signature verification | ✅ caido-plugin | [cosign](https://github.com/sigstore/cosign) | Keyless verification against the `issuer` and `identity` declared in the entry |

**Required ⇒ blocks merge.** **Informational ⇒ comment on PR but does not block.**

> Things the workflow deliberately does *not* do — sandboxing install hooks, mirroring upstream artifacts, blocking on CVE counts — live in [`intake/POLICY.md` § Non-goals](./intake/POLICY.md#non-goals). Read those before opening an issue asking for them; they are versioned decisions, not oversights.

The line between required and informational reflects pragmatism: existing wordlist/theme entries were not signed, and forcing retroactive signing would freeze the registry. Caido plugins, on the other hand, are *executable* code that runs in a security tool — they get the strictest path.

---

## Reviewing a PR (for maintainers)

1. Check that all required intake checks are green; if any fail, leave a comment pointing to the failed step
2. Click into the workflow run and download the SBOM and SAST report artifacts
3. Skim the SBOM for unexpected dependencies (cryptocurrency, telemetry, persistence libs)
4. Skim the SAST findings — even informational ones; reject if you see hardcoded creds or eval/exec on user input
5. Manually verify the description matches what the plugin actually does (`git clone` and read the README)
6. Approve and merge

If you need to override a failed check (e.g. a flaky network failure), document why in the PR review comment and re-run the workflow first. Do not merge with a red required check.

---

## Updating a plugin

If a plugin changes its repo URL, type, or release tag, open a PR updating the entry. Updates trigger the same intake checks as a new entry — including signature verification against the new tag.

---

## Removing a plugin

A weekly **Stale Entry Check** workflow (`.github/workflows/stale-check.yml`) auto-opens an issue with the `stale-entry` label when an upstream repo is archived, deleted, made private, or has its declared release tag removed. If your entry shows up there, expect a maintainer to follow up with a removal PR within a few days.

You can also open an issue manually. Plugins get removed if:

- The source repo is deleted, archived, or made private
- The maintainer requests removal
- A security issue is discovered post-merge that cannot be patched in a reasonable timeframe
- The plugin is found to violate the policy (telemetry, miners, etc.)

Removals are first-come-first-served — any maintainer can merge a removal PR once an issue exists.

---

## Local intake testing

Before opening a PR, you can run the intake checks against your draft entry:

```bash
git clone https://github.com/ProwlrBot/csbx-registry
cd csbx-registry

# Drop your draft into a fixture file
cp registry.yaml /tmp/registry-with-mine.yaml
# ... edit /tmp/registry-with-mine.yaml ...

REGISTRY_FILE=/tmp/registry-with-mine.yaml ./tests/run-intake.sh
```

The harness exits 0 if your entry would pass, and non-zero with the failing check named otherwise.

---

## Code of conduct

Be helpful. Be specific. If you reject a plugin, explain what would make it acceptable. If you submit a plugin, respond to review comments rather than re-opening identical PRs.

---

## Project governance

How decisions get made, the no-self-merge rule, and how maintainers are added or removed live in [`GOVERNANCE.md`](./GOVERNANCE.md). Read it if you are interested in becoming a maintainer or want to understand who can merge what.
