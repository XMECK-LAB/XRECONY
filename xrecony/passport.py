from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_source_passport(source: Path, source_identity: str) -> dict[str, Any]:
    """Create a portable, metadata-only identity record for a source scope."""
    stat = source.stat()
    usage = shutil.disk_usage(source)
    anchor = {
        "resolved_path": str(source.resolve()),
        "device": getattr(stat, "st_dev", None),
        "inode": getattr(stat, "st_ino", None),
        "root_mtime_ns": getattr(stat, "st_mtime_ns", None),
        "platform": platform.system(),
    }
    anchor_bytes = json.dumps(anchor, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "format": "xrecony-source-passport-v1",
        "created_utc": _utc_now(),
        "source_identity": source_identity,
        "source_name": source.name or str(source),
        "source_path": str(source),
        "anchor": anchor,
        "anchor_sha256": hashlib.sha256(anchor_bytes).hexdigest(),
        "capacity": {"total": usage.total, "used": usage.used, "free": usage.free},
        "capabilities": {
            "readable": os.access(source, os.R_OK),
            "writable_observed": os.access(source, os.W_OK),
            "source_mutation_allowed": False,
            "evidence_depths": ["D0", "D1"],
            "resume_checkpoint_supported": True,
        },
        "connector": {
            "kind": "filesystem",
            "transport": "local-or-mounted",
            "network_inferred": str(source).startswith(("\\\\", "//")),
        },
    }


def verify_source_passport(passport: dict[str, Any], source: Path) -> dict[str, Any]:
    """Compare reconnect evidence without claiming immutable hardware identity."""
    try:
        stat = source.stat()
    except OSError as exc:
        return {"state": "unavailable", "matched": False, "reason": f"{type(exc).__name__}: {exc}"}
    observed = {
        "resolved_path": str(source.resolve()),
        "device": getattr(stat, "st_dev", None),
        "inode": getattr(stat, "st_ino", None),
        "root_mtime_ns": getattr(stat, "st_mtime_ns", None),
        "platform": platform.system(),
    }
    anchor = passport.get("anchor", {})
    stable_keys = ("resolved_path", "device", "inode", "platform")
    differences = {
        key: {"expected": anchor.get(key), "observed": observed.get(key)}
        for key in stable_keys
        if anchor.get(key) != observed.get(key)
    }
    return {
        "state": "matched" if not differences else "changed",
        "matched": not differences,
        "differences": differences,
        "observed_utc": _utc_now(),
    }
