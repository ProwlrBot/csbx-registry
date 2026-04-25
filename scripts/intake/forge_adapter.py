#!/usr/bin/env python3
"""
Forge adapter — abstracts away GitHub/GitLab/Codeberg differences for intake.

The original intake assumed GitHub. This module gives a small surface area
that the rest of the intake code can call without knowing which forge it is
talking to:

- parse_repo(url) -> Forge | None
- Forge.api_repo_url() -> str
- Forge.api_release_url(tag) -> str
- Forge.archive_tarball_url(tag) -> str

It is invoked from Python entrypoints (validate-schema.py, scan-stale-entries.py,
prefetch.py). The bash check-repo.sh / verify-signature.sh call into a small
CLI shim (`forge_adapter.py info <url>`) when they need forge metadata.

Currently supported forges: github.com, gitlab.com, codeberg.org. New forges
can be added by appending to FORGE_PATTERNS — each entry is a regex with
named groups (`slug`) and a forge identifier.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass

# (forge name, base host, regex). Order matters — first match wins.
FORGE_PATTERNS = [
    ("github",   "https://github.com",   re.compile(r"^https://github\.com/(?P<slug>[^/\s]+/[^/\s]+?)/?$")),
    ("gitlab",   "https://gitlab.com",   re.compile(r"^https://gitlab\.com/(?P<slug>[^?\s]+?)/?$")),
    ("codeberg", "https://codeberg.org", re.compile(r"^https://codeberg\.org/(?P<slug>[^/\s]+/[^/\s]+?)/?$")),
]

SUPPORTED_FORGES = tuple(f[0] for f in FORGE_PATTERNS)


@dataclass(frozen=True)
class Forge:
    name: str
    base_host: str
    slug: str
    repo_url: str

    def api_repo_url(self) -> str:
        if self.name == "github":
            return f"https://api.github.com/repos/{self.slug}"
        if self.name == "gitlab":
            # GitLab requires URL-encoded project path
            from urllib.parse import quote
            return f"https://gitlab.com/api/v4/projects/{quote(self.slug, safe='')}"
        if self.name == "codeberg":
            return f"https://codeberg.org/api/v1/repos/{self.slug}"
        raise ValueError(f"unknown forge: {self.name}")

    def api_release_url(self, tag: str) -> str:
        if self.name == "github":
            return f"https://api.github.com/repos/{self.slug}/releases/tags/{tag}"
        if self.name == "gitlab":
            from urllib.parse import quote
            project = quote(self.slug, safe="")
            return f"https://gitlab.com/api/v4/projects/{project}/releases/{tag}"
        if self.name == "codeberg":
            return f"https://codeberg.org/api/v1/repos/{self.slug}/releases/tags/{tag}"
        raise ValueError(f"unknown forge: {self.name}")

    def archive_tarball_url(self, tag: str) -> str:
        if self.name == "github":
            return f"https://github.com/{self.slug}/archive/refs/tags/{tag}.tar.gz"
        if self.name == "gitlab":
            return f"https://gitlab.com/{self.slug}/-/archive/{tag}/{self.slug.split('/')[-1]}-{tag}.tar.gz"
        if self.name == "codeberg":
            return f"https://codeberg.org/{self.slug}/archive/{tag}.tar.gz"
        raise ValueError(f"unknown forge: {self.name}")

    def is_archived(self, body: dict) -> bool:
        # GitHub: archived; GitLab: archived; Codeberg (Gitea): archived
        return bool(body.get("archived"))

    def is_private(self, body: dict) -> bool:
        if self.name == "gitlab":
            return body.get("visibility") == "private"
        return bool(body.get("private"))


def parse_repo(repo: str) -> Forge | None:
    if not isinstance(repo, str):
        return None
    for name, base, pattern in FORGE_PATTERNS:
        m = pattern.match(repo)
        if m:
            return Forge(name=name, base_host=base, slug=m.group("slug"), repo_url=repo)
    return None


def cli_info(url: str) -> int:
    forge = parse_repo(url)
    if not forge:
        print(json.dumps({"error": "url did not match any supported forge",
                          "supported": list(SUPPORTED_FORGES)}))
        return 1
    print(json.dumps({
        "forge": forge.name,
        "slug": forge.slug,
        "api_repo_url": forge.api_repo_url(),
    }))
    return 0


def cli_release(url: str, tag: str) -> int:
    forge = parse_repo(url)
    if not forge:
        print(json.dumps({"error": "unsupported forge", "url": url}))
        return 1
    print(json.dumps({
        "forge": forge.name,
        "release_url": forge.api_release_url(tag),
        "tarball_url": forge.archive_tarball_url(tag),
    }))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    info = sub.add_parser("info", help="emit JSON describing the forge for a repo URL")
    info.add_argument("url")
    rel = sub.add_parser("release", help="emit JSON with release/tarball URLs for a tag")
    rel.add_argument("url")
    rel.add_argument("tag")
    args = p.parse_args()

    if args.cmd == "info":
        return cli_info(args.url)
    if args.cmd == "release":
        return cli_release(args.url, args.tag)
    return 1


if __name__ == "__main__":
    sys.exit(main())
