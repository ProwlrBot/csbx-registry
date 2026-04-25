#!/usr/bin/env python3
"""
Prefetch upstream artifacts for every entry in registry.yaml into a local cache.

This is the offline / air-gap helper. It does NOT install anything; it stages
the bytes a downstream installer (csbx, your bash script, your engagement
playbook) needs to resolve installs without network access.

Default behavior:
    For each entry in registry.yaml:
      - If `release` is set, download the GitHub release source tarball
        (https://github.com/<slug>/archive/refs/tags/<tag>.tar.gz) into
        <cache>/<section>/<name>/source.tar.gz
      - For caido_plugins entries, also download the release's signature
        artifacts: cosign .sig + .pem, OR minisign .minisig depending on
        `signature.method`.

Each entry's cache directory carries a manifest.json with the resolved
upstream URLs and the SHA-256 of every downloaded file, so a downstream
installer can verify integrity before use.

Usage:
    python3 tools/prefetch.py --cache ./offline-cache
    python3 tools/prefetch.py --cache ./offline-cache --only caido_plugins
    python3 tools/prefetch.py --cache ./offline-cache --dry-run

Flags:
    --cache DIR     destination directory (default: ./offline-cache)
    --only SECTION  restrict to one section (pdtm_tools|plugins|caido_plugins)
    --dry-run       plan only — print what would be fetched, don't download
    --registry F    alternate registry.yaml path

Exits:
    0 on success (or in dry-run when planning succeeds)
    1 if any download fails (after attempting all entries)

Cosign offline verification note: this tool fetches the .sig/.pem so the
artifacts are present at install time. For air-gap cosign verify-blob, you
also need a pre-fetched Rekor bundle (cosign verify-blob --bundle <bundle>
--offline). See OFFLINE.md for the recommended pre-flight using
`cosign verify-blob --rekor-url ... --output-file ...` on an internet-
connected machine before transferring the cache to the air-gapped host.
"""
from __future__ import annotations

import argparse
import hashlib
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


def slug_for(repo: str) -> str | None:
    m = GITHUB_URL_RE.match(repo)
    if m:
        return m.group(1)
    if SLUG_RE.match(repo):
        return repo
    return None


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_release_metadata(slug: str, tag: str, token: str | None) -> dict | None:
    url = f"https://api.github.com/repos/{slug}/releases/tags/{tag}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


def download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, dest.open("wb") as f:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
        return True
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"[-] download failed: {url}: {e}", file=sys.stderr)
        if dest.exists():
            dest.unlink()
        return False


def plan_entry(section: str, name: str, entry: dict) -> list[tuple[str, str]]:
    """Return [(label, url), ...] of files this entry needs in the cache."""
    plan: list[tuple[str, str]] = []
    repo = entry.get("repo", "")
    slug = slug_for(repo) if repo else None
    release = entry.get("release")

    if not slug:
        return plan

    if release:
        plan.append(("source.tar.gz",
                     f"https://github.com/{slug}/archive/refs/tags/{release}.tar.gz"))

    if section == "caido_plugins" and entry.get("type") == "caido-plugin":
        # Defer signature-asset URLs to runtime release-API lookup; without it
        # we cannot know the asset names.
        method = (entry.get("signature") or {}).get("method")
        if method:
            plan.append((f"signature/{method}", "<release-api-lookup>"))

    return plan


def fetch_signature_assets(
    cache_dir: Path,
    section: str,
    name: str,
    entry: dict,
    token: str | None,
    dry_run: bool,
) -> tuple[int, int]:
    """Pull signature assets that depend on the live release JSON."""
    if section != "caido_plugins" or entry.get("type") != "caido-plugin":
        return (0, 0)
    sig = entry.get("signature") or {}
    method = sig.get("method")
    release = entry.get("release")
    if not method or not release:
        return (0, 0)
    slug = slug_for(entry.get("repo", "") or "")
    if not slug:
        return (0, 0)

    if dry_run:
        print(f"  [dry-run] would resolve signature assets for {section}/{name} (method={method})")
        return (1, 0)

    meta = fetch_release_metadata(slug, release, token)
    if not meta:
        return (1, 1)

    assets = meta.get("assets", []) or []
    targets: list[tuple[str, str]] = []
    if method == "cosign":
        for a in assets:
            n = a.get("name", "")
            if n.endswith(".sig") or n.endswith(".pem"):
                targets.append((n, a.get("browser_download_url", "")))
    elif method == "minisign":
        for a in assets:
            n = a.get("name", "")
            if n.endswith(".minisig"):
                targets.append((n, a.get("browser_download_url", "")))

    fail = 0
    for fname, url in targets:
        if not url:
            fail += 1
            continue
        ok = download(url, cache_dir / fname)
        if not ok:
            fail += 1
    return (len(targets), fail)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--cache", default="./offline-cache")
    p.add_argument("--only", choices=["pdtm_tools", "plugins", "caido_plugins"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--registry", default="registry.yaml")
    args = p.parse_args()

    registry = Path(args.registry)
    if not registry.exists():
        print(f"[-] {registry} not found", file=sys.stderr)
        return 1

    data = yaml.safe_load(registry.read_text()) or {}
    cache_root = Path(args.cache)
    token = os.environ.get("GITHUB_TOKEN") or None

    failures = 0
    planned_total = 0

    sections = ("pdtm_tools", "plugins", "caido_plugins")
    for section in sections:
        if args.only and section != args.only:
            continue
        for name, entry in (data.get(section) or {}).items():
            if not isinstance(entry, dict):
                continue
            print(f"[*] {section}/{name}")
            entry_dir = cache_root / section / name
            plan = plan_entry(section, name, entry)
            planned_total += len(plan)

            manifest: dict = {
                "section": section,
                "name": name,
                "repo": entry.get("repo"),
                "release": entry.get("release"),
                "files": [],
            }

            for label, url in plan:
                if "<" in url:
                    # Defer to fetch_signature_assets below
                    continue
                target = entry_dir / label
                if args.dry_run:
                    print(f"  [dry-run] {label}: {url}")
                    continue
                if download(url, target):
                    digest = sha256_of(target)
                    manifest["files"].append({"path": str(target.relative_to(cache_root)),
                                              "url": url, "sha256": digest})
                else:
                    failures += 1

            sig_count, sig_fail = fetch_signature_assets(
                entry_dir, section, name, entry, token, args.dry_run
            )
            failures += sig_fail
            planned_total += sig_count

            if not args.dry_run and (entry_dir.exists() or manifest["files"]):
                entry_dir.mkdir(parents=True, exist_ok=True)
                (entry_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nPlanned {planned_total} files; failures: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
