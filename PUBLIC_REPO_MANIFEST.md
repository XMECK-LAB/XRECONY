# XRECONY — Public Repository Manifest

This repository is the curated public product surface for XRECONY.

## Branch model

- `main` — current product identity, discovery, documentation and direct downloads
- `release/1.x` — XRECONY 1.0 Engineering Preview
- `release/2.x` — XRECONY 2.0 Public Preview

## Release model

Deployable artifacts are published through GitHub Releases.

Current public release:

`v2.0.0 — XRECONY 2.0 Public Preview`

The public release contains the Windows installer, complete public ZIP, SHA-256 list, provenance, SBOM and source manifest.

## Public repository surface

### Root
- `README.md`
- `LICENSE.txt`
- `CITATION.cff`
- `SECURITY.md`
- `CHANGELOG.md`
- `PUBLIC_REPO_MANIFEST.md`

### Documentation
- `docs/ARCHITECTURE.md`
- `docs/BENCHMARKS.md`
- `docs/ROADMAP.md`
- `docs/HISTORY.md`
- `docs/XMECK_ECOSYSTEM.md`
- `docs/PUBLICATION.md`

### Visual / demo
- `assets/brand/`
- `assets/diagrams/`
- `assets/evidence/`
- `assets/screenshots/`
- `demo/`

## Excluded from the public surface

Generated build environments, PyInstaller internals, private governance, donor trees, private qualification logs, credentials, local workspaces and unpublished engineering history do not belong in this public repository.
## Live public demo

- Public website: https://xmeck-lab.github.io/XRECONY/
- GitHub Pages source: `main:/docs`
- Hosted entry point: `docs/index.html`
- `demo/index.html` is intentionally removed to prevent GitHub `/blob/` source-view confusion.
