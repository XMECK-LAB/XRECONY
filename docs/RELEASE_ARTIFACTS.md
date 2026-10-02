# XRECONY 2.0 — Release Artifacts

Canonical GitHub Release:

https://github.com/XMECK-LAB/XRECONY/releases/tag/v2.0.0

## Published assets

| Asset | Purpose |
|---|---|
| `XRECONY-2.0.0-Windows-x64-Setup.exe` | Windows installer |
| `XRECONY-2.0.0-Windows-x64-Public-Release.zip` | Complete public release carrier |
| `XRECONY-2.0.0-SHA256SUMS.txt` | Verification hashes |
| `XRECONY-2.0.0-PROVENANCE.json` | Release provenance |
| `XRECONY-2.0.0-SBOM.cdx.json` | CycloneDX software bill of materials |
| `XRECONY-2.0.0-SOURCE-MANIFEST.json` | Source manifest |

## Locked identities

Installer SHA-256:

```text
B55152AD66E95338FDE5DD9E836B0B1738AC9F42C59DB9FC7361794E39500F7E
```

Public release ZIP SHA-256:

```text
114B3585F235F6AA2D2DADEB042DE82FD03CA54A84F950E12FA62100B07A19E1
```

## Distribution model

The repository stores source-facing documentation and public presentation.

Deployable binary artifacts are distributed through GitHub Releases rather than duplicated into normal Git history.

The version branch `release/2.x` is the readable public product line for XRECONY 2.0. The tag `v2.0.0` is the exact release marker.
