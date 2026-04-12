# csbx-registry

Plugin registry for [CyberSandbox](https://github.com/kdairatchi/cybersandbox).

## Install a plugin

```bash
csbx install seclists
csbx install payloadsallthethings
csbx install nuclei-templates
csbx search fuzzing
```

## Submit a plugin

1. Create a git repo with your tool, wordlist, templates, or theme
2. Add a `csbx.yaml` at the repo root (see spec below)
3. Open a PR adding your entry to `registry.yaml`

### csbx.yaml spec

```yaml
name: my-plugin
version: "1.0.0"
type: tool              # tool | wordlist | nuclei-templates | theme | config
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

| Type | Where it installs | Use case |
|------|-------------------|----------|
| `tool` | `~/.csbx/plugins/tools/` | CLI binaries |
| `wordlist` | `~/.csbx/plugins/wordlists/` | Fuzzing / discovery lists |
| `nuclei-templates` | `~/.csbx/plugins/nuclei-templates/` | Scan templates |
| `theme` | `~/.csbx/plugins/themes/` | Shell themes / prompts |
| `config` | `~/.csbx/plugins/configs/` | Dotfiles, patterns, configs |

## Registry format

`registry.yaml` is a flat list. Each entry:

```yaml
my-plugin:
  repo: https://github.com/user/repo
  type: tool
  description: "Short description"
  size: "10MB"
  tags: [recon, xss]
```
