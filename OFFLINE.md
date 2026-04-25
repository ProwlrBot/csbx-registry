# Air-gap / offline workflow for csbx-registry

csbx-registry is a manifest pointing at upstream GitHub repos. There is no mirror, no CDN, no central artifact store — see [`intake/POLICY.md` § NG-2](./intake/POLICY.md#ng-2--mirroring-or-cdn-of-upstream-artifacts) for why. That looks like a problem for air-gapped engagements, but it is actually well-suited to them: the registry is a flat YAML file in a Git repo. Every entry's source of truth is reachable in advance.

This document is the recommended pre-flight workflow. It covers two phases:

- **Phase A — Stage** (run on an internet-connected machine): clone the registry, prefetch every release tarball + signature material your engagement needs, optionally pre-resolve cosign Rekor bundles for offline keyless verification.
- **Phase B — Operate** (run on the air-gapped host): use the staged cache. No network calls.

---

## Phase A — Stage

### A.1 Clone the registry at a known SHA

```bash
git clone https://github.com/ProwlrBot/csbx-registry
cd csbx-registry
git rev-parse HEAD                            # record this SHA in your engagement notes
```

The SHA pins the catalog. If maintainers update an entry tomorrow, your offline cache is unaffected.

### A.2 Prefetch every entry's artifacts

```bash
export GITHUB_TOKEN=...                        # optional, raises rate limits
python3 tools/prefetch.py --cache ./offline-cache
```

For each entry, `prefetch.py` downloads:

- The GitHub release source tarball (`https://github.com/<slug>/archive/refs/tags/<tag>.tar.gz`) — keyed off the entry's `release` field.
- For `caido_plugins`, the cosign signature bundle (`.sig` + `.pem`) **or** the minisign `.minisig`, depending on `signature.method`.

Each entry's directory under `offline-cache/<section>/<name>/` carries a `manifest.json` with the resolved upstream URLs and the SHA-256 of every file. Your installer should verify these before consuming.

#### Filtering

```bash
python3 tools/prefetch.py --cache ./cache --only caido_plugins
python3 tools/prefetch.py --cache ./cache --only pdtm_tools
python3 tools/prefetch.py --dry-run --cache ./cache  # plan only, no downloads
```

### A.3 Pre-resolve cosign Rekor bundles (caido_plugins only)

Cosign's keyless verify path normally calls Sigstore Rekor at runtime. For offline operation, pre-fetch a Rekor inclusion bundle on the connected machine:

```bash
# on the connected machine, for each caido_plugins entry:
SLUG=<owner>/<repo>
TAG=<release>
ARTIFACT=offline-cache/caido_plugins/<name>/<asset>
SIG=offline-cache/caido_plugins/<name>/<asset>.sig
CERT=offline-cache/caido_plugins/<name>/<asset>.pem

cosign verify-blob \
  --certificate-identity "<entry.signature.identity>" \
  --certificate-oidc-issuer "<entry.signature.issuer>" \
  --signature "$SIG" \
  --certificate "$CERT" \
  --bundle "offline-cache/caido_plugins/<name>/rekor-bundle.json" \
  "$ARTIFACT"
```

Once the bundle is on disk, the air-gapped host can re-run the same command with `--bundle` and `--offline`:

```bash
cosign verify-blob \
  --certificate-identity "<...>" \
  --certificate-oidc-issuer "<...>" \
  --bundle offline-cache/caido_plugins/<name>/rekor-bundle.json \
  --offline \
  "$ARTIFACT"
```

This works because Rekor's inclusion proof is cryptographically self-contained once captured.

### A.4 Pin the registry.yaml itself

Copy `registry.yaml` and your `.git/HEAD` SHA into the cache so the air-gapped host has the manifest, not just the artifacts:

```bash
cp registry.yaml offline-cache/registry.yaml
git rev-parse HEAD > offline-cache/REGISTRY_SHA
```

---

## Phase B — Operate (air-gapped)

### B.1 Resolve installs from the cache

Pseudo-code for an installer that reads the cache:

```bash
# (illustrative — adapt to your actual installer)
ENTRY=seclists
SECTION=plugins
TARBALL=offline-cache/$SECTION/$ENTRY/source.tar.gz
EXPECTED=$(jq -r --arg p "$SECTION/$ENTRY/source.tar.gz" \
  '.files[] | select(.path == $p) | .sha256' \
  offline-cache/$SECTION/$ENTRY/manifest.json)

ACTUAL=$(sha256sum "$TARBALL" | cut -d' ' -f1)
[ "$EXPECTED" = "$ACTUAL" ] || { echo "tampered cache" >&2; exit 1; }

tar -xzf "$TARBALL" -C ~/.csbx/plugins/wordlists/$ENTRY
```

### B.2 Verify cosign signatures offline (caido_plugins)

Use the Rekor bundle staged in A.3:

```bash
cosign verify-blob \
  --certificate-identity "<...>" \
  --certificate-oidc-issuer "<...>" \
  --bundle offline-cache/caido_plugins/<name>/rekor-bundle.json \
  --offline \
  offline-cache/caido_plugins/<name>/<artifact>
```

`--offline` blocks Rekor lookups; the inclusion proof in the bundle is sufficient.

### B.3 Verify minisign signatures offline

Always offline by design — minisign verification is local cryptography against the public key in the entry:

```bash
minisign -V \
  -p <inline-public-key-or-staged-key-file> \
  -m offline-cache/caido_plugins/<name>/<artifact> \
  -x offline-cache/caido_plugins/<name>/<artifact>.minisig
```

---

## Limitations

- `pdtm_tools` entries use `go install` rather than release tarballs. Pre-staging a Go module proxy is out of scope here; use [Athens](https://github.com/gomods/athens) or `GOFLAGS=-mod=vendor` with a vendored module.
- An entry that does not declare a `release` (most `plugins` entries pin to upstream's default branch) is fetched via `archive/refs/tags/<release>` only when `release` is present. For non-tagged plugins you will need a separate snapshot strategy (e.g. `git clone --depth 1` against your own internal mirror).
- The cache does not include the SBOM/SAST artifacts CI generates per PR. Persisted attestations (roadmap feature-3) will provide a stable URL set you can prefetch separately.

---

## Smoke-testing the workflow

The smallest entry by size is `gf-patterns` (~50KB). To dry-run end-to-end:

```bash
python3 tools/prefetch.py --cache /tmp/csbx-smoke --dry-run --only plugins 2>&1 | grep -A1 gf-patterns
```

For an actual download, omit `--dry-run`. (Most `plugins` entries do not declare `release`, so the planner will skip them; that is expected — see Limitations above.)

---

**Last reviewed:** 2026-04-25
