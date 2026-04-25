# csbx-registry schema migrations

`registry.yaml` carries a top-level `version` field. This document is the contract for evolving that version: how migrations are written, how the deprecation window works, and how downstream consumers (the csbx CLI resolver, third-party indexers) survive a bump.

The current schema version is **`1`**.

---

## Why versioned schemas matter

The csbx CLI resolver lives in a separate repo. When this registry's shape changes, the CLI's resolver code must change in lockstep — or downstream users break the next time they run `csbx install`. A `version` field plus this migration process give us:

1. **A canary.** Resolvers can refuse to operate on an unknown future version with a clear error instead of silently producing wrong results.
2. **A deprecation window.** New shape lands and old shape is still accepted for ≥1 minor cycle. CLI maintainers have time to ship the resolver update.
3. **A migration audit trail.** Every bump is a numbered, dated entry in this file, with the diff and rationale captured before the migration is applied.

---

## When to bump `version`

Bump when you change the **structural** contract — anything a downstream consumer would key off:

| Change | Bump? |
|--------|-------|
| Add a new optional top-level field (e.g. `policy_version`) | No — backward compatible. |
| Add a new optional per-entry field (e.g. `platforms`, `attestations`) | No — backward compatible. |
| Add a new entry section (e.g. `nuclei_packages`) | No — old consumers ignore unknown sections. |
| Rename a required field (e.g. `repo` → `upstream_url`) | **Yes.** |
| Change the type of an existing field | **Yes.** |
| Change the meaning of an existing field's accepted values | **Yes.** |
| Add a new required field to existing entries | **Yes** — old consumers will see entries they cannot validate. |
| Restructure an existing nested shape | **Yes.** |

Don't bump for cosmetic edits, comment-only changes, or new informational fields.

If you are unsure, it is much cheaper to bump-and-document than to ship a silent break.

---

## How to bump `version` (the workflow)

A schema-bumping PR is a "policy change" by the rules in [`GOVERNANCE.md`](./GOVERNANCE.md): two approvers, 72-hour minimum review window. The PR must contain all of the following, in this order:

### 1. Add a `MIGRATION-N` entry below

Use the template at the bottom of this file. State **before**, **after**, and **rationale**. State which entries (if any) need to be rewritten. State the deprecation window (default: one minor cycle ≈ 30 days, but explicit).

### 2. Update `scripts/intake/validate-manifest.py`'s `SUPPORTED_VERSIONS`

Add the new version. Keep the immediately-prior version in the set with a `DEPRECATED_VERSIONS` membership so it still passes intake but emits a `[!] manifest: version=N is deprecated; bump to N+1 by <date>` warning to stderr.

### 3. Update `scripts/intake/migrate-registry.py`

Add a step function `migrate_<from>_to_<to>(data: dict) -> dict` that performs the mechanical transformation. Idempotent. No network calls. The function operates on a parsed YAML dict; it does **not** read or write files itself.

### 4. Update `intake/registry-contract.schema.json`

Bump the `$id` and the `version` field's enum (or constant). If you keep accepting both versions during the deprecation window, fork the schema into per-version sub-schemas under `$defs` and dispatch on `$ref` from a `oneOf` at the root.

### 5. Apply the migration to `registry.yaml`

Run `python3 scripts/intake/migrate-registry.py --from N --to N+1 < registry.yaml > registry.new.yaml`, eyeball the diff, replace the file. Bump `policy_version` to today's date.

### 6. Notify the csbx CLI maintainers

Open an issue in the CyberSandbox CLI repo titled `[csbx-registry] schema bump: vN → vN+1`. Link this PR. Include the deprecation deadline.

### 7. Add migration tests

Add fixtures under `tests/fixtures/migrations/<N>_to_<N+1>/`:

- `before.yaml` — a representative pre-migration registry
- `after.yaml` — the expected post-migration registry
- `test_migration_<N>_to_<N+1>.py` (or extend the runner) — applies the step function to `before.yaml` and asserts equality with `after.yaml`

---

## Deprecation window mechanics

When schema vN+1 lands:

| Day | State |
|-----|-------|
| 0 | vN+1 is the current schema; vN still passes intake with a stderr deprecation warning. |
| 0 → ~30 (default) | Both versions accepted. Resolvers can ship vN+1 support at their own pace. |
| ~30 | vN moves from `DEPRECATED_VERSIONS` to a removed set. Validator rejects vN with a "see MIGRATION-N+1" pointer. |

The window is **at least** 30 days but maintainers can extend it (with a comment in the relevant `MIGRATION-N` entry below) if a major downstream consumer is not ready.

---

## Migration log

### MIGRATION-0 · v1 baseline (2026-04-12)

> **From:** N/A
> **To:** v1
> **Status:** current

Initial schema. Three sections (`pdtm_tools`, `plugins`, `caido_plugins`), per-entry shape documented in [`intake/registry-contract.schema.json`](./intake/registry-contract.schema.json). Subsequent backward-compatible additions (`policy_version`, `platforms`, `attestations`) were absorbed without a version bump per the table above.

### MIGRATION-1 · template (do not apply — example only)

This is a worked example so a future maintainer can see the shape. It is **not** committed as a real migration.

> **From:** v1
> **To:** v2 (hypothetical)
> **Status:** template
> **Deprecation deadline:** N/A — example only

**Shape change.** The `signature` block uses an internally-tagged discriminator (`method`); a future v2 might switch to externally-tagged for ergonomics:

```yaml
# v1
signature:
  method: cosign
  issuer: https://...
  identity: https://...

# v2 (hypothetical)
signature:
  cosign:
    issuer: https://...
    identity: https://...
```

**Migration step (in `scripts/intake/migrate-registry.py`):**

```python
def migrate_1_to_2(data: dict) -> dict:
    for section in ("plugins", "caido_plugins"):
        for name, entry in (data.get(section) or {}).items():
            sig = entry.get("signature")
            if not isinstance(sig, dict) or "method" not in sig:
                continue
            method = sig.pop("method")
            entry["signature"] = {method: sig}
    data["version"] = 2
    return data
```

**Rationale (rejected for v1).** The discriminator change reduces ambiguity but is not currently worth the breakage. Documented here so the v2 PR has a starting point.

---

## Template — copy this when adding a new migration entry

```markdown
### MIGRATION-N · <one-line summary> (<YYYY-MM-DD>)

> **From:** vN
> **To:** vN+1
> **Status:** active | reverted | superseded
> **Deprecation deadline:** <YYYY-MM-DD>

**Shape change.** <Before/after diff or table>.

**Migration step.** See `migrate_<N>_to_<N+1>` in `scripts/intake/migrate-registry.py`.

**Affected entries.** <List, or "all" / "none">

**Rationale.** <Why now, what breaks if we don't, what the alternative was>

**Resolver coordination.** <Issue link to the csbx CLI repo's tracking issue>
```

---

**Last reviewed:** 2026-04-25
