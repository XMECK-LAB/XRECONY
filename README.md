<p align="center">
  <img src="assets/brand/xrecony-hero.png" width="100%" alt="XRECONY â€” Understand your data before you move it">
</p>

<p align="center">
  <strong>XRECONY 2.0 Â· Public Preview</strong><br>
  Windows Â· Read-only reconstruction Â· Evidence-backed Â· Active development
</p>

<p align="center">
  <a href="#download">Download</a> Â·
  <a href="#what-xrecony-does">What it does</a> Â·
  <a href="#engineering-evidence">Evidence</a> Â·
  <a href="#roadmap">Roadmap</a> Â·
  <a href="demo/index.html">Demo</a>
</p>

---

## Why XRECONY exists

Storage keeps getting cheaper. Understanding long-lived data estates does not.

**XRECONY** is a Windows reconstruction workspace for readable data estates. It builds an evidence-backed structural twin in a **separate workspace** so you can understand what exists, how it relates, where duplication or version candidates may exist, what changed, and what can be safely copied elsewhere â€” **without intentionally modifying the source**.

> **THE SOURCE REMAINS THE SOURCE.**

XRECONY is useful for messy external drives, archive folders, migration sets, mounted NAS/SMB shares, old laptop estates and backup collections where understanding should come before reorganization.

<p align="center"><img src="assets/diagrams/workflow.svg" width="96%" alt="XRECONY workflow"></p>

## What XRECONY does

- **Reconstructs readable storage** into a separate structural workspace.
- **Builds multiple views** across source, type, timeline and recovery perspectives.
- **Surfaces duplicate and version-family candidates** as evidence to investigate â€” not automatic deletion decisions.
- **Compares generations** and reports structural drift.
- **Produces evidence and exports** for review and verification.
- **Supports copy-first Safe Realization** to a separate destination in 2.0.
- **Fails honestly**: a completed run is not automatically called verified.

## What XRECONY is not

XRECONY is not a backup system, deleted-file recovery utility, damaged-disk repair tool or destructive deduplicator. Dedicated tools in those categories solve different primary problems. XRECONY focuses on **understanding the wider readable data estate before change**.

<p align="center"><img src="assets/diagrams/architecture.svg" width="96%" alt="XRECONY public architecture"></p>

## Current capability boundary

| Capability | State |
|---|---|
| Local folders | **Supported** |
| Mounted HDD / SSD | **Supported** |
| Mounted SMB / NAS | **Supported** |
| Portable metadata manifest | **Supported** |
| Structural reconstruction | **Supported** |
| Source / Type / Timeline / Recovery views | **Supported** |
| Duplicate candidates | **Supported** |
| Version-family candidates | **Supported** |
| Generation comparison | **Supported** |
| Drift detection | **Supported** |
| Evidence / report exports | **Supported** |
| Safe copy realization | **Supported in 2.0** |
| Native Google Drive | **Unavailable pending release qualification** |
| Native Dropbox | **Unavailable pending release qualification** |
| Native OneDrive / SharePoint | **Unavailable pending release qualification** |
| 25 TB / ~45 min objective | **Research target â€” not proven** |

## Engineering evidence

These are **founder-machine observations**, not universal speed claims.

<p align="center">
  <img src="assets/evidence/benchmark-109gb.svg" width="48%" alt="109 GB verified workload">
  <img src="assets/evidence/benchmark-193gb.svg" width="48%" alt="193 GB drift-detected workload">
</p>

The 193 GB result is intentionally retained. XRECONY surfaced **DRIFT DETECTED** rather than manufacturing a clean verification state.

Data size alone does not define reconstruction complexity. Object population, directory topology, storage behavior, metadata shape, cache state and workload composition materially affect runtime.

Full evidence: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)

## Product screenshots

<p align="center">
  <img src="assets/screenshots/xrecony-2-dark.png" width="48%" alt="XRECONY dark interface">
  <img src="assets/screenshots/xrecony-2-light.png" width="48%" alt="XRECONY light interface">
</p>

## Download

The public repository separates **source** from **release binaries**.

Normal users should use **GitHub Releases** and download the Windows release artifact. Developers can inspect the source tree and tests.

Planned public release line:

- **v1.0.0 â€” Engineering Preview**: first public engineering release derived from the mature pre-2.0 working lineage.
- **v2.0.0 â€” Public Preview**: current product line.

The internal Surface/XRF/RSF/V4â€“V11/LSDR terminology remains engineering history and is intentionally not used as public version numbering.

## Roadmap

XRECONY is useful today, but the original reconstruction vision is **not finished**. Current engineering focuses on:

- controlled multi-TB benchmark qualification;
- stronger content-level duplicate evidence;
- better version-family differentiation;
- deeper relationship and drift explanations;
- provider-specific authentication / pagination / revocation qualification;
- signed Windows artifacts and clean-machine lifecycle;
- progress toward a longer-term 25 TB-class reconstruction research objective.

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Research lineage

XRECONY is associated with the broader **XPADI-SGDS** survivability and structural-reconstruction research direction. XPADI-SGDS remains the wider system-level research architecture; XRECONY is the practical reconstruction software surface.

Research evidence: https://raajmandale.github.io/XPADI-SGDS/lsdr/

## XMECK-AI LAB

XRECONY is published as part of the **XMECK-AI LAB** software ecosystem.

Created by **Raaj Mandale**.

> Public repository licensing / rights-holder finalization must be completed before general public publication. The supplied historical license is preserved rather than silently rewritten.

