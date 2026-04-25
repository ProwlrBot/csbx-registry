#!/usr/bin/env python3
"""
Generate a browsable INDEX.md from registry.yaml.

Each entry becomes a card with: name, type, description, repo link, size,
tags, and (where applicable) release / signature method / attestation
links. Entries are grouped by type with a table of contents at the top
so users can jump-list by category instead of grepping the YAML.

Usage:
    python3 tools/generate-index.py                         # writes ./INDEX.md
    python3 tools/generate-index.py --out custom.md
    python3 tools/generate-index.py --registry alt.yaml --out alt.md

The output is deterministic for a given input — running twice produces
identical bytes — so a CI job can re-run on every push and detect drift.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

TYPE_GROUPS = [
    ("caido-plugin",     "Caido plugins",        "🛰️", "Strict-tier — cosign signature + blocking SAST"),
    ("tool",             "Tools",                "🔧", ""),
    ("wordlist",         "Wordlists",            "📚", ""),
    ("nuclei-templates", "Nuclei templates",     "🌀", ""),
    ("yara-rules",       "YARA rules",           "🔬", ""),
    ("sigma",            "Sigma rules",          "📡", ""),
    ("threat-intel",     "Threat intel",         "🛡️", ""),
    ("config",           "Configs",              "⚙️", ""),
    ("theme",            "Shell themes",         "🎨", ""),
]


def slugify(s: str) -> str:
    return s.replace("-", "").replace("_", "")


def render_entry(name: str, entry: dict) -> str:
    repo = entry.get("repo", "")
    desc = entry.get("description", "")
    size = entry.get("size", "")
    tags = entry.get("tags") or []
    release = entry.get("release")
    method = (entry.get("signature") or {}).get("method") if entry.get("type") == "caido-plugin" else None
    platforms = entry.get("platforms") or []
    attest = entry.get("attestations") or {}

    lines = [f"#### `{name}`"]
    if desc:
        lines.append(f"{desc}")
    bullets: list[str] = []
    if repo:
        bullets.append(f"**Repo:** [{repo}]({repo})")
    if size:
        bullets.append(f"**Size:** {size}")
    if release:
        bullets.append(f"**Release:** `{release}`")
    if method:
        method_badge = "✅ cosign keyless" if method == "cosign" else "🔑 minisign"
        bullets.append(f"**Signature:** {method_badge}")
    if platforms:
        bullets.append(f"**Platforms:** " + ", ".join(f"`{p}`" for p in platforms))
    if tags:
        bullets.append(f"**Tags:** " + " ".join(f"`{t}`" for t in tags))

    badges: list[str] = []
    if attest.get("sbom_url"):
        badges.append(f"[![SBOM](https://img.shields.io/badge/SBOM-cyclonedx-blue)]({attest['sbom_url']})")
    if attest.get("sast_url"):
        badges.append(f"[![SAST](https://img.shields.io/badge/SAST-semgrep-green)]({attest['sast_url']})")
    if attest.get("cve_url"):
        badges.append(f"[![CVE](https://img.shields.io/badge/CVE-grype-orange)]({attest['cve_url']})")
    if badges:
        bullets.append("**Attestations:** " + " ".join(badges))

    if bullets:
        lines.append("")
        for b in bullets:
            lines.append(f"- {b}")

    return "\n".join(lines)


def render_pdtm(name: str, entry: dict) -> str:
    repo = entry.get("repo", "")
    repo_url = f"https://github.com/{repo}" if repo and "/" in repo and "://" not in repo else repo
    install_path = entry.get("go_install_path", "")
    version = entry.get("version", "latest")
    # Some entries already include @latest in go_install_path; don't double up.
    install_cmd = (
        f"go install {install_path}"
        if "@" in install_path
        else f"go install {install_path}@{version}"
    )
    lines = [
        f"#### `{name}`",
        "",
        f"- **Repo:** [{repo}]({repo_url})" if repo else "",
        f"- **Install:** `{install_cmd}`" if install_path else "",
        f"- **Version pin:** `{version}`",
    ]
    return "\n".join(l for l in lines if l)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", default="registry.yaml")
    p.add_argument("--out", default="INDEX.md")
    args = p.parse_args()

    data = yaml.safe_load(Path(args.registry).read_text()) or {}
    parts: list[str] = []

    parts.append("# csbx-registry catalog\n")
    parts.append(
        "_Auto-generated from [`registry.yaml`](./registry.yaml) on every push to `main`. "
        "Do not edit by hand — your changes will be overwritten by the next run of "
        "`tools/generate-index.py`._\n"
    )
    parts.append(f"- **Schema version:** `{data.get('version', 'unknown')}`")
    parts.append(f"- **Policy version:** `{data.get('policy_version', 'unknown')}`")
    parts.append(f"- **Last data update:** `{data.get('updated', 'unknown')}`\n")

    pdtm = data.get("pdtm_tools") or {}
    plugins = data.get("plugins") or {}
    caido = data.get("caido_plugins") or {}

    # Bucket plugins by type
    by_type: dict[str, list[tuple[str, dict]]] = {}
    for name, entry in plugins.items():
        if not isinstance(entry, dict):
            continue
        by_type.setdefault(entry.get("type", "other"), []).append((name, entry))
    for name, entry in caido.items():
        if not isinstance(entry, dict):
            continue
        by_type.setdefault("caido-plugin", []).append((name, entry))
    for k in by_type:
        by_type[k].sort(key=lambda nv: nv[0])

    parts.append("## Table of contents\n")
    parts.append(f"- [pdtm tools](#pdtm-tools) — {len(pdtm)} entries")
    for type_key, label, icon, _ in TYPE_GROUPS:
        count = len(by_type.get(type_key, []))
        if count == 0 and type_key != "caido-plugin":
            continue
        anchor = label.lower().replace(" ", "-")
        parts.append(f"- {icon} [{label}](#{anchor}) — {count} entries")
    parts.append("")

    parts.append("## pdtm tools\n")
    parts.append("Go tools resolved through `csbx pdtm <name>`. These are not subject to "
                 "the cosign/SAST gate; they install via the Go toolchain at user time.\n")
    for name in sorted(pdtm.keys()):
        parts.append(render_pdtm(name, pdtm[name]))
        parts.append("")

    for type_key, label, icon, subhead in TYPE_GROUPS:
        entries = by_type.get(type_key, [])
        if not entries and type_key != "caido-plugin":
            continue
        parts.append(f"## {icon} {label}\n")
        if subhead:
            parts.append(f"_{subhead}_\n")
        if not entries:
            parts.append("_No entries yet._\n")
            continue
        for name, entry in entries:
            parts.append(render_entry(name, entry))
            parts.append("")

    parts.append("---")
    parts.append(f"\n_{len(pdtm) + sum(len(v) for v in by_type.values())} entries total. "
                 f"See [`CONTRIBUTING.md`](./CONTRIBUTING.md) to add yours._")

    Path(args.out).write_text("\n".join(parts) + "\n")
    print(f"[+] wrote {args.out} ({len(parts)} sections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
