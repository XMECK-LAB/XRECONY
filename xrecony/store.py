from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS records (
  record_id TEXT PRIMARY KEY,
  parent_id TEXT,
  name TEXT NOT NULL,
  rel_path TEXT NOT NULL,
  abs_path TEXT NOT NULL,
  kind TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime_ns INTEGER,
  created_ns INTEGER,
  extension TEXT NOT NULL,
  category TEXT NOT NULL,
  year TEXT NOT NULL,
  status TEXT NOT NULL,
  error TEXT NOT NULL,
  type_path TEXT NOT NULL,
  time_path TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_rel_path ON records(rel_path);
CREATE INDEX IF NOT EXISTS idx_records_parent ON records(parent_id);
CREATE INDEX IF NOT EXISTS idx_records_category ON records(category);
CREATE INDEX IF NOT EXISTS idx_records_year ON records(year);
CREATE INDEX IF NOT EXISTS idx_records_kind ON records(kind);
CREATE INDEX IF NOT EXISTS idx_records_name ON records(name);
"""


class GenerationStore:
    def __init__(self, generation_dir: Path):
        self.generation_dir = generation_dir
        self.generation_dir.mkdir(parents=True, exist_ok=False)
        self.db_path = generation_dir / "records.sqlite3"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA)

    def insert_many(self, rows: Iterable[tuple[Any, ...]]) -> None:
        self.conn.executemany(
            """INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.conn.close()


def ensure_workspace(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "generations").mkdir(exist_ok=True)
    marker = workspace / "workspace.json"
    if not marker.exists():
        _atomic_json(marker, {"format": "xrecony-workspace-v1", "source_mutation": False})


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def activate_generation(workspace: Path, generation_id: str) -> None:
    target = workspace / "generations" / generation_id / "generation.json"
    if not target.is_file():
        raise ValueError("Generation does not exist or is incomplete")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("state") != "certified":
        raise ValueError("Only certified generations may be activated")
    active = workspace / "active_generation.json"
    previous = None
    if active.exists():
        previous = json.loads(active.read_text(encoding="utf-8")).get("generation_id")
    if previous and previous != generation_id:
        _atomic_json(workspace / "previous_generation.json", {"generation_id": previous})
    _atomic_json(active, {"generation_id": generation_id})
    append_audit(workspace, "generation_activated", {"from": previous, "to": generation_id})


def rollback_generation(workspace: Path) -> str:
    previous_file = workspace / "previous_generation.json"
    if not previous_file.exists():
        raise ValueError("No previous generation is available")
    previous = json.loads(previous_file.read_text(encoding="utf-8")).get("generation_id")
    if not previous:
        raise ValueError("No previous generation is available")
    current = active_generation_dir(workspace)
    current_id = current.name if current else None
    activate_generation(workspace, previous)
    append_audit(workspace, "generation_rollback", {"from": current_id, "to": previous})
    return previous


def can_rollback(workspace: Path) -> bool:
    previous_file = workspace / "previous_generation.json"
    if not previous_file.exists():
        return False
    try:
        previous = json.loads(previous_file.read_text(encoding="utf-8")).get("generation_id")
    except (OSError, json.JSONDecodeError):
        return False
    return bool(previous and (workspace / "generations" / previous / "generation.json").is_file())


def append_audit(workspace: Path, event: str, details: dict[str, Any]) -> None:
    record = {
        "event": event,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "details": details,
    }
    path = workspace / "audit_events.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_audit(workspace: Path, limit: int = 200) -> list[dict[str, Any]]:
    path = workspace / "audit_events.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(rows))


def list_generations(workspace: Path) -> list[dict[str, Any]]:
    active_id = None
    active = workspace / "active_generation.json"
    if active.exists():
        active_id = json.loads(active.read_text(encoding="utf-8")).get("generation_id")
    result = []
    root = workspace / "generations"
    if not root.exists():
        return result
    for path in root.iterdir():
        manifest = path / "generation.json"
        if manifest.is_file():
            item = json.loads(manifest.read_text(encoding="utf-8"))
            item["active"] = item.get("generation_id") == active_id
            result.append(item)
    return sorted(result, key=lambda item: item.get("created_utc", ""), reverse=True)


def generation_diff(workspace: Path, left_id: str, right_id: str, limit: int = 500) -> dict[str, Any]:
    left = workspace / "generations" / left_id / "records.sqlite3"
    right = workspace / "generations" / right_id / "records.sqlite3"
    if not left.is_file() or not right.is_file():
        raise ValueError("Both generation databases are required")
    left_conn = sqlite3.connect(left)
    right_conn = sqlite3.connect(right)
    try:
        columns = ("kind", "size", "mtime_ns", "category", "year", "status")
        left_rows = {
            row[0]: dict(zip(columns, row[1:]))
            for row in left_conn.execute(
                "SELECT rel_path,kind,size,mtime_ns,category,year,status FROM records"
            )
        }
        right_rows = {
            row[0]: dict(zip(columns, row[1:]))
            for row in right_conn.execute(
                "SELECT rel_path,kind,size,mtime_ns,category,year,status FROM records"
            )
        }
    finally:
        left_conn.close()
        right_conn.close()
    left_paths, right_paths = set(left_rows), set(right_rows)
    added = sorted(right_paths - left_paths)
    removed = sorted(left_paths - right_paths)
    changed_paths = sorted(path for path in left_paths & right_paths if left_rows[path] != right_rows[path])
    changed = []
    for path in changed_paths[:limit]:
        before, after = left_rows[path], right_rows[path]
        fields = {
            key: {"before": before[key], "after": after[key]}
            for key in columns
            if before[key] != after[key]
        }
        changed.append({"path": path, "fields": fields})
    return {
        "from": left_id,
        "to": right_id,
        "counts": {"added": len(added), "removed": len(removed), "changed": len(changed_paths)},
        "added": added[:limit],
        "removed": removed[:limit],
        "changed": changed,
        "truncated": any(len(group) > limit for group in (added, removed, changed_paths)),
    }


def active_generation_dir(workspace: Path) -> Path | None:
    active = workspace / "active_generation.json"
    if not active.exists():
        return None
    generation_id = json.loads(active.read_text(encoding="utf-8")).get("generation_id")
    if not generation_id:
        return None
    path = workspace / "generations" / generation_id
    return path if path.is_dir() else None
