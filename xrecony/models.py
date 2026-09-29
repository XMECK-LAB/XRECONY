from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScopeSeal:
    source: str
    workspace: str
    source_identity: str
    created_utc: str
    policy_version: str = "xrecony-xrf-one-d0d1-v1"
    evidence_depth: str = "D0/D1"
    source_mutation_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanProgress:
    state: str = "idle"
    stage: str = "ready"
    source: str = ""
    workspace: str = ""
    generation_id: str = ""
    records: int = 0
    files: int = 0
    directories: int = 0
    links: int = 0
    errors: int = 0
    metadata_bytes: int = 0
    logical_bytes: int = 0
    allocated_bytes: int = 0
    mode: str = "normal"
    adapter: str = "python-optimized-scandir-xrf1"
    integrity_state: str = "pending"
    started_utc: str | None = None
    finished_utc: str | None = None
    elapsed_seconds: float = 0.0
    records_per_second: float = 0.0
    progress_percent: float = 0.0
    message: str = "Ready"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())
