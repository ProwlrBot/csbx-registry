# csbx-registry Governance

This document codifies how decisions get made, who can merge what, and how the project handles maintainer changes. It complements [`CONTRIBUTING.md`](./CONTRIBUTING.md) (which covers contribution mechanics) and [`intake/POLICY.md`](./intake/POLICY.md) (which covers what the intake workflow checks).

If you are a contributor opening a PR, you do not need to read this. If you are or want to be a maintainer, this is the contract.

---

## Roles

| Role | Who | What they can do |
|------|-----|------------------|
| **Contributor** | Anyone | Open PRs, comment, file issues, propose changes |
| **Maintainer** | Listed in `.github/CODEOWNERS` (when present) and the README's maintainers section | Review and merge PRs, label/triage issues, override CI failures per [`intake/POLICY.md`](./intake/POLICY.md) |
| **Owner** | The single account that holds `Admin` on the GitHub repo | Add/remove maintainers, change branch protection, rotate secrets |

The Owner role is administrative only. All technical decisions are made by maintainers as a group.

---

## How decisions are made

### Routine PRs (new entry, doc fix, bug fix)

1. Author opens a PR.
2. CI runs ([`Plugin Intake Check`](./.github/workflows/intake.yml)).
3. **One** maintainer who is **not the author** reviews and merges.
4. If CI is red, the maintainer asks the author to fix or — only for verifiable infra failures — applies a documented override per [`intake/POLICY.md`](./intake/POLICY.md#maintainer-override).

### Policy changes (intake threshold, new required check, schema change)

1. Author opens a PR that updates `intake/POLICY.md`, the workflow, the scripts, **and** bumps `policy_version` in `registry.yaml` (CI enforces the bump via `validate-manifest.py`).
2. **Two** maintainers must approve. At least one must not be the author.
3. The PR stays open at minimum 72 hours after the second approval to allow other maintainers to weigh in.
4. Authors of in-flight registry-entry PRs are notified by a comment if the policy change would affect their entry.

### Schema migrations (registry.yaml `version` bump)

Follow the deprecation process in [`MIGRATIONS.md`](./MIGRATIONS.md) (when added). Treat as a policy change for review purposes.

### Disputes

When maintainers disagree:

1. State the disagreement in a single PR or issue thread, not multiple places.
2. If a path forward is not reached within 7 days, the Owner casts a tie-breaking vote — but only after every involved maintainer has stated their position in writing.
3. Whichever side loses documents the rejected option in [`intake/POLICY.md`](./intake/POLICY.md) under "Non-goals" if it is the kind of decision worth preserving for future revisits.

The Owner does not get to break ties on questions of *fact* — only on questions of *direction*. CI output, audit logs, and security findings are decided by what they say, not by who reads them.

---

## No self-merge

A maintainer **cannot** merge a PR they authored, period. This is enforced by:

1. **Branch protection** on `main`: at least one approving review required from someone other than the author.
2. **Convention**: a maintainer who needs their own PR merged asks another maintainer in the PR thread; they do not click `Merge` themselves even if branch protection would let them.
3. **CODEOWNERS** (when present): listed maintainers are auto-requested on relevant paths so review surface is always covered.

If branch protection is ever bypassed (e.g. an admin force-push), the responsible maintainer must open a follow-up issue documenting why within 24 hours. Repeated bypass without justification is grounds for removal.

---

## Maintainer rotation

### Adding a maintainer

A new maintainer is added when:

1. They have authored at least 5 substantive PRs that landed cleanly (no major rework requested).
2. An existing maintainer nominates them in an issue titled `Maintainer nomination: <handle>`.
3. At least one other maintainer approves in the issue thread, and no maintainer objects within 14 days.
4. The Owner adds them to the GitHub team / `CODEOWNERS` and updates the README maintainer list.

There is no probation period — once added, a maintainer has the same authority as any other.

### Removing a maintainer

A maintainer is removed when:

1. **They request it** — voluntarily stepping down. Effective immediately on Owner action.
2. **They are inactive** — no review activity, no issue activity, no commit activity for 6 months. Any maintainer may open a removal issue; if no objection from the inactive maintainer within 30 days, the Owner removes them.
3. **They violate the no-self-merge rule, the override rule, or the code of conduct** — any maintainer may open a removal issue; standard policy-change review applies (two approvers, 72-hour minimum window, plus the involved maintainer is recused).

Removed maintainers retain contributor status. Their past commits and reviews remain attributed.

### Why the bus factor matters

This project currently has a small contributor footprint. The risk is not malice — it is hit-by-bus, fatigue, or unrelated life events. The rotation rules above exist so:

- Adding maintainers is mechanical, not political (no probation, no veto-by-silence).
- Removing inactive maintainers is mechanical, not awkward (the inactive maintainer does not have to be reachable to be removed — silence is the signal).

We would rather have 6 maintainers who each review one PR a week than 2 maintainers who burn out.

---

## Review etiquette

- Reject PRs with **specific** feedback. "Doesn't meet bar" is not a review; "the SAST output shows two ERROR-level findings on lines X and Y, please address before re-requesting" is.
- Approve PRs by stating **what** you reviewed, not just "LGTM". The convention: one sentence for routine PRs, a short list for policy changes.
- When you cannot review (out of capacity, conflict of interest), say so explicitly so other maintainers know to pick it up.

---

## Amendments

This document is amended via the same process as a policy change (two approvers, 72-hour minimum window). Material amendments bump the `policy_version` at the top of `registry.yaml`.

---

**Last reviewed:** 2026-04-25
