# csbx-registry

Plugin registry for [CyberSandbox](https://github.com/kdairatchi/cybersandbox) and a community catalog for [Caido](https://caido.io) plugins.

## Install a plugin

```bash
csbx install seclists
csbx install payloadsallthethings
csbx install nuclei-templates
csbx search fuzzing
```

## Submit a plugin

1. Create a git repo with your tool, wordlist, templates, theme, or Caido plugin
2. Add a `csbx.yaml` at the repo root (see spec below). For Caido plugins, also ship a Caido manifest in your release artifact.
3. Open a PR adding your entry to `registry.yaml`
4. The **Plugin Intake Check** workflow runs automatically — see [`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`intake/POLICY.md`](./intake/POLICY.md) for what it does and how to pass.

You do **not** need to be a CyberBox author. Any well-maintained plugin meeting the intake policy is welcome.

### csbx.yaml spec

```yaml
name: my-plugin
version: "1.0.0"
type: tool              # tool | wordlist | nuclei-templates | theme | config | caido-plugin
description: "What it does"
author: your-github-handle

# Optional install hooks (run as bash)
install: |
  go build -o bin/mytool ./cmd/mytool

# Optional: binaries to symlink into PATH
binaries:
  - bin/mytool

# Optional: cleanup on uninstall
uninstall: |
  echo "cleaned up"

tags: [recon, xss, fuzzing]
```

### Plugin types

| Type | Where it installs | Use case | Intake policy |
|------|-------------------|----------|---------------|
| `tool` | `~/.csbx/plugins/tools/` | CLI binaries | Standard |
| `wordlist` | `~/.csbx/plugins/wordlists/` | Fuzzing / discovery lists | Standard |
| `nuclei-templates` | `~/.csbx/plugins/nuclei-templates/` | Scan templates | Standard |
| `theme` | `~/.csbx/plugins/themes/` | Shell themes / prompts | Standard |
| `config` | `~/.csbx/plugins/configs/` | Dotfiles, patterns, configs | Standard |
| `caido-plugin` | `~/.caido/plugins/` (resolved by `csbx install --caido`) | Plugins for the Caido HTTP toolkit | **Strict** — cosign signature, SBOM, and SAST required to merge |

**Standard** = schema check, repo verify, SBOM generation, informational SAST.
**Strict** = standard plus required cosign signature verification and blocking SAST on HIGH/CRITICAL findings.

See [`intake/POLICY.md`](./intake/POLICY.md) for the full breakdown.

## Registry format

`registry.yaml` is a flat list grouped by section. Each entry:

```yaml
my-plugin:
  repo: https://github.com/user/repo
  type: tool
  description: "Short description"
  size: "10MB"
  tags: [recon, xss]
```

Caido plugins additionally declare a `release` tag and a `signature` block — see CONTRIBUTING for the full schema.

## Project documents

| Doc | What it covers |
|-----|----------------|
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | How to add or update entries |
| [`intake/POLICY.md`](./intake/POLICY.md) | What the intake workflow checks and why |
| [`GOVERNANCE.md`](./GOVERNANCE.md) | Decision-making, no-self-merge, maintainer rotation |
| [`MIGRATIONS.md`](./MIGRATIONS.md) | Schema migration process and version-bump workflow |
| [`OFFLINE.md`](./OFFLINE.md) | Air-gap / offline workflow (prefetch, cosign Rekor bundle pre-resolution) |
| [`INDEX.md`](./INDEX.md) | **Auto-generated** browsable catalog with cards per entry (do not edit) |
