from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Callable


_VERSION_TOKEN = re.compile(r"(?i)(?:^|[\s_.-])(copy|final|draft|rev|ver|version|v)?[\s_.-]*(\d+)(?:$|[\s_.-])")


def _family_signature(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = _VERSION_TOKEN.sub(" # ", f" {stem} ")
    stem = re.sub(r"\d+", "#", stem)
    return " ".join(re.sub(r"[_\-.]+", " ", stem).split())


def _line(handle, digest, item: dict[str, Any]) -> None:
    payload = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    handle.write(payload)
    digest.update(payload)


def build_fabric(
    generation_dir: Path,
    source_identity: str,
    *,
    cancel_event: threading.Event | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Compile a disk-streamed CRG so large estates do not require an in-memory graph."""
    cancel_event = cancel_event or threading.Event()
    if cancel_event.is_set():
        raise InterruptedError("Reconstruction cancelled before Fabric compilation")

    conn = sqlite3.connect(generation_dir / "records.sqlite3")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS fabric_family(record_id TEXT, signature TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fabric_family_signature ON fabric_family(signature)")
    conn.execute("DELETE FROM fabric_family")

    node_path = generation_dir / "crg_nodes.jsonl"
    relation_path = generation_dir / "crg_relationships.jsonl"
    node_digest = hashlib.sha256()
    relation_digest = hashlib.sha256()
    category_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    node_samples = []
    relation_samples = []
    diagnostics = []
    node_count = relation_count = 0

    def check_cancel() -> None:
        if cancel_event.is_set():
            raise InterruptedError("Reconstruction cancelled during Fabric compilation")

    check_cancel()
    try:
      with node_path.open("wb") as node_handle, relation_path.open("wb") as relation_handle:
        total_records = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        rows = conn.execute(
            "SELECT record_id,parent_id,name,rel_path,kind,size,mtime_ns,created_ns,"
            "extension,category,year,status,error,type_path,time_path "
            "FROM records ORDER BY rel_path COLLATE BINARY"
        )
        family_batch = []
        for row in rows:
            if node_count % 1000 == 0:
                check_cancel()
                if on_progress:
                    on_progress("nodes", node_count, total_records)
            evidence = ["D0:path", "D0:name", "D0:type"]
            if row["mtime_ns"] is not None:
                evidence.append("D0:mtime")
            if row["parent_id"]:
                evidence.append("D1:parent")
                relation = {
                    "kind": "contained-by", "from": row["record_id"], "to": row["parent_id"],
                    "evidence": ["D1:parent"],
                }
                _line(relation_handle, relation_digest, relation)
                relation_count += 1
                if len(relation_samples) < 25:
                    relation_samples.append(relation)
            signature = _family_signature(row["name"]) if row["kind"] == "file" else ""
            realities = {
                "source": row["rel_path"],
                "type": row["type_path"],
                "timeline": row["time_path"],
                "recovery": (
                    f"Recovery/Attention/{row['rel_path']}"
                    if row["status"] != "placed"
                    else f"Recovery/Stable/{row['rel_path']}"
                ),
            }
            node = {
                "object_id": row["record_id"],
                "source_identity": source_identity,
                "parent_id": row["parent_id"],
                "observed": {
                    "name": row["name"], "path": row["rel_path"], "kind": row["kind"],
                    "size": row["size"], "mtime_ns": row["mtime_ns"], "created_ns": row["created_ns"],
                    "extension": row["extension"], "category": row["category"], "year": row["year"],
                    "status": row["status"], "error": row["error"],
                },
                "reconstructed_realities": realities,
                "placement": {
                    "selected": "source", "evidence": evidence,
                    "confidence": round(min(0.99, 0.45 + 0.12 * len(evidence)), 2),
                    "alternatives": ["type", "timeline", "recovery"], "content_read": False,
                },
                "family_signature": signature,
            }
            _line(node_handle, node_digest, node)
            node_count += 1
            if len(node_samples) < 25:
                node_samples.append(node)
            category_counts[row["category"]] += 1
            year_counts[row["year"]] += 1
            status_counts[row["status"]] += 1
            if signature:
                family_batch.append((row["record_id"], signature))
                if len(family_batch) >= 5000:
                    conn.executemany("INSERT INTO fabric_family VALUES (?,?)", family_batch)
                    family_batch.clear()
            if row["status"] != "placed" and len(diagnostics) < 5000:
                diagnostics.append({
                    "code": "OBJECT_UNRESOLVED", "severity": "warning",
                    "object_id": row["record_id"], "path": row["rel_path"],
                    "basis": row["error"] or row["status"], "evidence_depth": "D0",
                })
        if family_batch:
            conn.executemany("INSERT INTO fabric_family VALUES (?,?)", family_batch)
        conn.commit()
        if on_progress:
            on_progress("nodes", node_count, total_records)

        family_groups = 0
        family_member_total = conn.execute(
            "SELECT COALESCE(SUM(count),0) FROM ("
            "SELECT COUNT(*) count FROM fabric_family GROUP BY signature HAVING COUNT(*)>1)"
        ).fetchone()[0]
        family_rows = conn.execute(
            "SELECT f.record_id,f.signature FROM fabric_family f "
            "JOIN (SELECT signature FROM fabric_family GROUP BY signature HAVING COUNT(*)>1) g "
            "ON g.signature=f.signature ORDER BY f.signature,f.record_id"
        )
        prior_signature = None
        family_done = 0
        for record_id, signature in family_rows:
            if family_done % 1000 == 0:
                check_cancel()
                if on_progress:
                    on_progress("families", family_done, family_member_total)
            if signature != prior_signature:
                family_groups += 1
                prior_signature = signature
            group_id = hashlib.sha256(("family\0" + signature).encode()).hexdigest()[:20]
            relation = {
                "kind": "version-family-candidate", "from": record_id, "to": group_id,
                "evidence": ["D0:filename-normalization"],
            }
            _line(relation_handle, relation_digest, relation)
            relation_count += 1
            family_done += 1

        duplicate_groups = 0
        duplicate_member_total = conn.execute(
            "SELECT COALESCE(SUM(count),0) FROM (SELECT COUNT(*) count FROM records "
            "WHERE kind='file' AND size>0 GROUP BY size,extension HAVING COUNT(*)>1)"
        ).fetchone()[0]
        duplicate_rows = conn.execute(
            "SELECT r.record_id,r.size,r.extension FROM records r "
            "JOIN (SELECT size,extension FROM records WHERE kind='file' AND size>0 "
            "GROUP BY size,extension HAVING COUNT(*)>1) g "
            "ON g.size=r.size AND g.extension=r.extension "
            "WHERE r.kind='file' ORDER BY r.size,r.extension,r.record_id"
        )
        prior_duplicate = None
        duplicate_done = 0
        for record_id, size, extension in duplicate_rows:
            if duplicate_done % 1000 == 0:
                check_cancel()
                if on_progress:
                    on_progress("duplicates", duplicate_done, duplicate_member_total)
            key = (size, extension)
            if key != prior_duplicate:
                duplicate_groups += 1
                prior_duplicate = key
            group_id = hashlib.sha256(f"duplicate\0{size}\0{extension}".encode()).hexdigest()[:20]
            relation = {
                "kind": "duplicate-candidate", "from": record_id, "to": group_id,
                "evidence": ["D0:size", "D0:extension"], "content_confirmed": False,
            }
            _line(relation_handle, relation_digest, relation)
            relation_count += 1
            duplicate_done += 1
        check_cancel()
        if on_progress:
            on_progress("complete", node_count, node_count)
    except BaseException:
        conn.close()
        for incomplete_path in (node_path, relation_path):
            try:
                incomplete_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    else:
        conn.close()

    header_core = {
        "format": "xrecony-counterfactual-reconstruction-graph-v1",
        "storage": "streamed-jsonl",
        "source_identity": source_identity,
        "source_mutation_performed": False,
        "evidence_depth": "D0/D1",
        "realities": ["source", "type", "timeline", "recovery"],
        "node_count": node_count,
        "relationship_count": relation_count,
        "diagnostic_count": len(diagnostics),
        "node_stream_sha256": node_digest.hexdigest(),
        "relationship_stream_sha256": relation_digest.hexdigest(),
    }
    graph_digest = hashlib.sha256(
        json.dumps(header_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    header = {**header_core, "graph_sha256": graph_digest}
    graph = {
        "header": header,
        "node_stream": node_path.name,
        "relationship_stream": relation_path.name,
        "node_samples": node_samples,
        "relationship_samples": relation_samples,
    }
    (generation_dir / "reconstruction_graph.json").write_text(
        json.dumps(graph, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )
    universe = {
        "format": "xrecony-data-universe-v1",
        "source_identity": source_identity,
        "dimensions": {"categories": dict(category_counts), "years": dict(year_counts), "states": dict(status_counts)},
        "topology": {
            "objects": node_count, "relationships": relation_count,
            "version_families": family_groups, "duplicate_candidate_groups": duplicate_groups,
        },
    }
    (generation_dir / "data_universe.json").write_text(json.dumps(universe, indent=2, sort_keys=True), encoding="utf-8")
    diagnostics_report = {
        "format": "xrecony-integrity-diagnostics-v1",
        "boundary": "Metadata-grounded signals only; no repair or leak claim is made.",
        "summary": dict(Counter(item["code"] for item in diagnostics)),
        "signals": diagnostics,
        "truncated": len(diagnostics) >= 5000,
    }
    (generation_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics_report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return {"graph": header, "universe": universe, "diagnostics": diagnostics_report}
