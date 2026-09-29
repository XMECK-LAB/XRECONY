from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()


def emit_event(generation_dir: Path, event: str, details: dict[str, Any] | None = None) -> None:
    record = {
        "sequence_event": event,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "details": details or {},
    }
    with _LOCK:
        with (generation_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_events(generation_dir: Path, limit: int = 500) -> list[dict[str, Any]]:
    path = generation_dir / "events.jsonl"
    if not path.is_file():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 5000)):]:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result
