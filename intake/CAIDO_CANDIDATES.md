# Caido plugin candidates

Working list of Caido plugins worth chasing for inclusion in `caido_plugins:`.
**Authoritative when**: an entry on this list either lands in `registry.yaml`
or is documented here with a "blocked on …" note explaining the obstacle.

This file is a living document; it is not authoritative for the registry
(`registry.yaml` is). Maintainers update this list as candidates progress.

---

## Status legend

- ✅ **Landed** — entry is live in `registry.yaml`
- 🟡 **Awaiting signature** — code is good; release isn't cosign/minisign-signed yet
- 🟠 **SAST blocking** — semgrep finds ERROR-level patterns that need fixing upstream
- ⏸ **Stale upstream** — repo went archived or no recent activity
- 🔍 **Researched, not yet contacted** — surfaced in roadmap research, no upstream conversation yet

---

## Candidates

| Status | Plugin | Repo | Notes |
|--------|--------|------|-------|
| 🔍 | (placeholder — fill in via the [Caido plugin candidate](../.github/ISSUE_TEMPLATE/caido-plugin-candidate.md) issue template) | — | Use the issue template to nominate. |

---

## Process

1. **Nominate** via the [Caido plugin candidate issue template](../.github/ISSUE_TEMPLATE/caido-plugin-candidate.md). Fills the strict-tier readiness checklist.
2. **Reach out** to the upstream author for any unchecked boxes (most commonly: cosign keyless signing).
3. **PR** when all boxes are checked. Reference the candidate issue in the PR body.
4. **Update this file** when the entry lands or stalls — keep the "blocked on …" note accurate so future maintainers don't re-do research.

---

## Why this list exists separately from `registry.yaml`

The registry is for entries that have *passed* strict intake. Candidates that haven't yet — including candidates that are blocked on third-party action — would degrade catalog signal if we added them with skip flags. This file gives them a documented home without polluting the manifest.

It also makes the F1 acceptance criterion "POLICY.md updated with concrete examples linking to a merged caido-plugin PR" achievable incrementally: as candidates land, link them from this file and from the relevant POLICY.md examples.

---

**Last reviewed:** 2026-04-25
