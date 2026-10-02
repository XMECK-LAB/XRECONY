# XRECONY 2.0 — Install & Verify

## Download

Windows installer:

`XRECONY-2.0.0-Windows-x64-Setup.exe`

Direct download:

https://github.com/XMECK-LAB/XRECONY/releases/download/v2.0.0/XRECONY-2.0.0-Windows-x64-Setup.exe

Complete public package:

`XRECONY-2.0.0-Windows-x64-Public-Release.zip`

Direct download:

https://github.com/XMECK-LAB/XRECONY/releases/download/v2.0.0/XRECONY-2.0.0-Windows-x64-Public-Release.zip

## Verify SHA-256

Installer:

```text
B55152AD66E95338FDE5DD9E836B0B1738AC9F42C59DB9FC7361794E39500F7E
```

Public package:

```text
114B3585F235F6AA2D2DADEB042DE82FD03CA54A84F950E12FA62100B07A19E1
```

PowerShell example:

```powershell
Get-FileHash ".\XRECONY-2.0.0-Windows-x64-Setup.exe" -Algorithm SHA256
```

Do not install if the hash differs from the published value.

## Install

Run the Windows installer normally.

XRECONY is delivered as a native Windows desktop application.

## Start a reconstruction

Choose:

1. a readable source;
2. a separate writable XRECONY workspace.

The source and workspace must remain separate.

## Product safety model

```text
SOURCE ≠ WORKSPACE ≠ REALIZATION DESTINATION
```

Reconstruction is read-oriented against the source. Safe Realization is a separate, explicit copy operation to a separate destination.
