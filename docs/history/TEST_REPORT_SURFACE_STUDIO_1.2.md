# XRECONY Surface Studio 1.2 — Validation Report

Date: 2026-07-23  
Status: **FINAL UI CANDIDATE — OWNER ACCEPTANCE PENDING**

## Scope

Presentation and Windows desktop-shell changes only. The XRECONY V4.5.1 reconstruction engine, APIs, evidence, receipts, verification, rollback and source-read-only boundary remain unchanged.

## Delivered

- Automatic maximized Windows application launch.
- Height-aware Command cockpit at 100% application scale.
- Concurrent visibility of source controls and live reconstruction instrument on common desktop viewports.
- XRF neural field with source stack, inbound metadata packets, compilation lattice, outbound view packets, scan beam and protocol telemetry.
- Visual state bound to the real capture, accounting, preparation, compilation, integrity, certification, completed, cancelled and failed stages.
- Code-native animation; no uploaded reference GIF is embedded.
- Reduced-motion accessibility retained.
- Standalone PyInstaller target remains free of pywebview, pythonnet, NuGet and .NET bridge dependencies.

## Automated validation

Command:

`python3 -m unittest discover -s tests -v`

Result:

- 19 tests run.
- 19 passed.
- 0 failures.
- 0 errors.

Additional checks:

- JavaScript syntax: passed.
- Local `/api/status` smoke test: passed.
- Surface 1.2 HTML smoke markers: passed.

## Owner acceptance

1. Launch `START_XRECONY.bat` or the newly built Surface 1.2 EXE.
2. Keep Windows display scaling and application zoom at 100%.
3. Confirm the Command screen shows source/workspace controls and the live instrument together.
4. Run the 16 GB source, then the external-drive source.
5. Confirm the source, packet, compile, integrity and certification visual phases change with the measured run.
6. Confirm Explore, History, Verify, Speed, Intelligence and Map retain their data and controls.
7. Run `RUN_TESTS.bat`.

Final UI lock should occur only after this owner acceptance pass.
