# audit-archive

This orphan branch is the durable home for SBOM and SAST artifacts generated
by the intake workflow. Layout:

```
<section>/<entry-name>/<release>/
  sbom.cdx.json
  sast.json     (caido_plugins only; informational for other types)
  manifest.json
```

Each `manifest.json` records the upstream repo, release tag, intake commit
SHA, and timestamps for provenance. Files are committed by the
`Persist Attestations` workflow on every push to `main` that touches
`registry.yaml`.

This branch is **not** human-edited. Auto-commits only.
