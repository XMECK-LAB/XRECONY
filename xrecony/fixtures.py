from __future__ import annotations

import json
from pathlib import Path


EXTENSIONS = (".pdf", ".docx", ".jpg", ".mp4", ".xlsx", ".zip", ".txt", ".py")


def build_scale_fixture(target: str, records: int, payload_bytes: int = 0) -> dict:
    """Create a deterministic metadata-scale fixture; never overwrite a non-empty directory."""
    root = Path(target).expanduser().resolve()
    if records < 1:
        raise ValueError("records must be at least 1")
    if payload_bytes < 0 or payload_bytes > 1024 * 1024:
        raise ValueError("payload_bytes must be between 0 and 1 MiB per file")
    if root.exists() and any(root.iterdir()):
        raise ValueError("fixture target must be empty")
    root.mkdir(parents=True, exist_ok=True)
    payload = b"X" * payload_bytes
    for index in range(records):
        bucket = root / f"batch-{index // 1000:05d}"
        bucket.mkdir(exist_ok=True)
        extension = EXTENSIONS[index % len(EXTENSIONS)]
        (bucket / f"xrecony-fixture-{index:09d}{extension}").write_bytes(payload)
    manifest = {
        "format": "xrecony-scale-fixture-v1",
        "records_requested": records,
        "payload_bytes_per_file": payload_bytes,
        "purpose": "Metadata-scale validation only; not representative of a real-world corpus.",
    }
    (root / "XRECONY_FIXTURE.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"target": str(root), **manifest}
