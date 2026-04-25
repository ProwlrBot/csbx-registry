---
name: Caido plugin candidate
about: Nominate a Caido plugin for inclusion in the registry. Ships a checklist for the strict-tier intake.
title: "[caido-candidate] <plugin name> (<owner>/<repo>)"
labels: ["caido-candidate"]
assignees: []
---

## Plugin

- **Name:** <slug — what users will type after `csbx install --caido`>
- **Repo:** https://github.com/<owner>/<repo>
- **Why this plugin?** <one sentence on what it does + who would use it>

## Strict intake readiness checklist

The registry's strict tier ([`intake/POLICY.md`](../intake/POLICY.md)) requires every Caido plugin to pass:

- [ ] **Schema** — entry has `release`, `manifest`, and `signature` fields
- [ ] **Repo accessibility** — public, not archived, declared release tag exists
- [ ] **SBOM** — syft can generate a CycloneDX SBOM from the source tree
- [ ] **SAST blocking** — semgrep auto + `intake/semgrep-caido.yml` produce zero ERROR findings on the source
- [ ] **Signature verification** — release ships either:
  - Cosign keyless: `<artifact>`, `<artifact>.sig`, `<artifact>.pem` plus the OIDC `issuer` + `identity` we declare in the entry, **OR**
  - Minisign: `<artifact>.minisig` plus a published `public_key`

If any of the boxes above is unchecked, the candidate is not yet landable as a `caido-plugin` entry. The two common gaps are:

1. **No cosign signing in the release workflow.** Fix per [`intake/POLICY.md` § Check 5 — Signature verification](../intake/POLICY.md#check-5--signature-verification-required-for-caido-plugin-skipped-for-others) — the policy doc has a copy-pasteable workflow.
2. **SAST findings.** Open the failing PR and address the findings; in most cases they are real (eval/exec on user input, hardcoded creds).

## When the plugin is ready

Open a PR adding the entry to `caido_plugins:` in `registry.yaml`. Reference this issue in the PR body. A maintainer will review, the workflow will run, and if everything passes the entry lands.

If you are an author and would like help wiring cosign keyless signing into your release workflow, comment on this issue — maintainers will pair on it.
