# Contributing to csbx-registry

## Adding a plugin

1. Fork this repo
2. Add your entry to `registry.yaml` (alphabetical within its type section)
3. Your plugin repo must have a `csbx.yaml` at root
4. Open a PR with:
   - Plugin name
   - What it does
   - Approximate download size
   - Link to your repo

## Review criteria

- Plugin repo must be public
- `csbx.yaml` must be valid (name, type, description at minimum)
- Install hooks must not require root/sudo
- No cryptocurrency miners, adware, or telemetry
- Offensive tools are fine — this is a security research platform

## Updating a plugin

If a plugin changes its repo URL or type, open a PR updating the entry.

## Removing a plugin

Open an issue. Plugins get removed if:
- The source repo is deleted or archived
- The maintainer requests removal
- Security issues are found in install hooks
