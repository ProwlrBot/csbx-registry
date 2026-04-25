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


def slug_for(repo: str) -> str | None:
    m = GITHUB_URL_RE.match(repo)
    if m:
        return m.group(1)
    if SLUG_RE.match(repo):
        return repo
    return None


def scan(name: str, section: str, entry: dict, token: str | None) -> None:
    repo = entry.get("repo", "")
    if not repo:
        return

    slug = slug_for(repo)
    if not slug:
        emit(name, section, repo, "404", "URL did not parse as GitHub slug")
        return

    code, body = fetch(f"https://api.github.com/repos/{slug}", token)
    if code != 200:
        emit(name, section, repo, "404", f"GitHub API returned {code} for {slug}")
        return

    if body.get("archived"):
        emit(name, section, repo, "archived", f"{slug} is archived upstream")
        return
    if body.get("private"):
        emit(name, section, repo, "private", f"{slug} is private upstream")
        return

    release = entry.get("release")
    if entry.get("type") == "caido-plugin" and release:
        code, _ = fetch(f"https://api.github.com/repos/{slug}/releases/tags/{release}", token)
        if code != 200:
            emit(name, section, repo, "missing-release",
                 f"release tag {release} not found in {slug}")


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
