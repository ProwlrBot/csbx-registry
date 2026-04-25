#!/usr/bin/env python3
"""
Walk registry.yaml and emit JSON Lines for stale entries.

A registry entry is "stale" if any of these are true:
- the upstream GitHub repo returns non-200 from the API
- the upstream repo is archived
- the upstream repo is private (i.e. became private since landing)
- for caido_plugins entries with a `release` field, the tag is no longer published

Output (stdout, one JSON object per line):
    {"name":"...","section":"...","repo":"...","reason":"archived|private|404|missing-release","detail":"..."}

Inputs (env):
    REGISTRY_FILE   path to registry.yaml (default: registry.yaml)
    GITHUB_TOKEN    optional but strongly recommended for rate-limit headroom
    DRY_RUN         if "true", skip network calls and emit a synthetic
                    finding for every entry (lets the workflow self-test)

Exits:
    0 — scan completed
    2 — invariant violation (couldn't read registry, etc.)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

GITHUB_URL_RE = re.compile(r"^https://github\.com/([^/\s]+/[^/\s]+?)/?$")
SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

# Multi-forge: scan-stale uses the forge_adapter for non-GitHub URLs. To keep
# this script self-contained, we duplicate the minimal forge dispatch here.
SUPPORTED_FORGE_HOSTS = {
    "github.com":   ("github",   lambda slug: f"https://api.github.com/repos/{slug}",
                                 lambda slug, tag: f"https://api.github.com/repos/{slug}/releases/tags/{tag}"),
    "gitlab.com":   ("gitlab",   lambda slug: f"https://gitlab.com/api/v4/projects/{slug.replace('/', '%2F')}",
                                 lambda slug, tag: f"https://gitlab.com/api/v4/projects/{slug.replace('/', '%2F')}/releases/{tag}"),
    "codeberg.org": ("codeberg", lambda slug: f"https://codeberg.org/api/v1/repos/{slug}",
                                 lambda slug, tag: f"https://codeberg.org/api/v1/repos/{slug}/releases/tags/{tag}"),
}
MULTI_FORGE_RE = re.compile(
    r"^https://(github\.com|gitlab\.com|codeberg\.org)/([^/\s]+/[^/\s]+?)/?$"
)


def emit(name: str, section: str, repo: str, reason: str, detail: str) -> None:
    print(json.dumps({
        "name": name,
        "section": section,
        "repo": repo,
        "reason": reason,
        "detail": detail,
    }))


def fetch(url: str, token: str | None) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except (urllib.error.URLError, TimeoutError, ValueError):
        return 0, {}


def resolve_forge(repo: str) -> tuple[str, str, str, str] | None:
    """Return (forge_name, slug, repo_api_url, release_url_template_marker)."""
    m = MULTI_FORGE_RE.match(repo)
    if m:
        host, slug = m.group(1), m.group(2)
        forge_name, repo_url_fn, release_url_fn = SUPPORTED_FORGE_HOSTS[host]
        return forge_name, slug, repo_url_fn(slug), "release"
    if SLUG_RE.match(repo):
        # pdtm-tools form (slug only) — assume GitHub.
        forge_name, repo_url_fn, release_url_fn = SUPPORTED_FORGE_HOSTS["github.com"]
        return forge_name, repo, repo_url_fn(repo), "release"
    return None


def scan(name: str, section: str, entry: dict, token: str | None) -> None:
    repo = entry.get("repo", "")
    if not repo:
        return

    resolved = resolve_forge(repo)
    if not resolved:
        emit(name, section, repo, "404", "URL did not parse as a supported forge")
        return
    forge_name, slug, repo_api, _ = resolved

    code, body = fetch(repo_api, token)
    if code != 200:
        emit(name, section, repo, "404", f"{forge_name} API returned {code} for {slug}")
        return

    is_private = (
        body.get("visibility") == "private"
        if forge_name == "gitlab"
        else bool(body.get("private"))
    )
    if body.get("archived"):
        emit(name, section, repo, "archived", f"{slug} ({forge_name}) is archived upstream")
        return
    if is_private:
        emit(name, section, repo, "private", f"{slug} ({forge_name}) is private upstream")
        return

    release = entry.get("release")
    if entry.get("type") == "caido-plugin" and release:
        host_to_release_fn = {h: fns[2] for h, fns in SUPPORTED_FORGE_HOSTS.items()}
        # Find the host from forge_name
        host = next((h for h, (n, _, _) in SUPPORTED_FORGE_HOSTS.items() if n == forge_name), "github.com")
        release_url = host_to_release_fn[host](slug, release)
        code, _ = fetch(release_url, token)
        if code != 200:
            emit(name, section, repo, "missing-release",
                 f"release tag {release} not found in {slug} ({forge_name})")


def main() -> int:
    registry_path = Path(os.environ.get("REGISTRY_FILE", "registry.yaml"))
    if not registry_path.exists():
        print(f"[-] {registry_path} not found", file=sys.stderr)
        return 2

    token = os.environ.get("GITHUB_TOKEN") or None
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"

    data = yaml.safe_load(registry_path.read_text()) or {}

    sections = ("pdtm_tools", "plugins", "caido_plugins")
    for section in sections:
        for name, entry in (data.get(section) or {}).items():
            if not isinstance(entry, dict):
                continue
            if dry_run:
                emit(name, section, entry.get("repo", ""), "dry-run",
                     f"DRY_RUN=true; not contacting GitHub for {name}")
                continue
            scan(name, section, entry, token)

    return 0


if __name__ == "__main__":
    sys.exit(main())
