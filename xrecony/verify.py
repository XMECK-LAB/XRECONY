from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .scanner import _account_and_hash


def verify_generation(generation_dir_text: str) -> dict:
    generation_dir = Path(generation_dir_text).expanduser().resolve()
    manifest_path = generation_dir / "generation.json"
    receipt_path = generation_dir / "receipt.json"
    db_path = generation_dir / "records.sqlite3"
    if not all(path.is_file() for path in (manifest_path, receipt_path, db_path)):
        return {"valid": False, "reason": "Required generation files are missing"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    receipt_hash = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt_hash != manifest.get("receipt_sha256"):
        return {"valid": False, "reason": "Receipt hash does not match manifest"}
    conn = sqlite3.connect(db_path)
    try:
        accounting = _account_and_hash(conn)
    finally:
        conn.close()
    stream_hash = accounting.pop("record_stream_sha256")
    if accounting != receipt.get("accounting"):
        return {"valid": False, "reason": "Accounting does not match record database", "actual": accounting}
    if stream_hash != receipt.get("record_stream_sha256"):
        return {"valid": False, "reason": "Record stream hash mismatch"}
    graph_path = generation_dir / "reconstruction_graph.json"
    if receipt.get("fabric"):
        if not graph_path.is_file():
            return {"valid": False, "reason": "Counterfactual Reconstruction Graph is missing"}
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        claimed = receipt["fabric"].get("graph_sha256")
        header = graph.get("header", {})
        embedded = header.get("graph_sha256")
        node_path = generation_dir / graph.get("node_stream", "")
        relation_path = generation_dir / graph.get("relationship_stream", "")
        if not node_path.is_file() or not relation_path.is_file():
            return {"valid": False, "reason": "CRG evidence streams are missing"}
        if hashlib.sha256(node_path.read_bytes()).hexdigest() != header.get("node_stream_sha256"):
            return {"valid": False, "reason": "CRG node stream hash mismatch"}
        if hashlib.sha256(relation_path.read_bytes()).hexdigest() != header.get("relationship_stream_sha256"):
            return {"valid": False, "reason": "CRG relationship stream hash mismatch"}
        header_core = {key: value for key, value in header.items() if key != "graph_sha256"}
        actual = hashlib.sha256(
            json.dumps(header_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if claimed != embedded or actual != claimed:
            return {"valid": False, "reason": "Counterfactual Reconstruction Graph hash mismatch"}
    terminal = sum(accounting.get(key, 0) for key in ("placed", "unresolved", "excluded", "errors", "quarantined"))
    if terminal != accounting.get("records"):
        return {"valid": False, "reason": "Total-accounting invariant failed"}
    return {"valid": True, "reason": "Generation receipt, accounting and record stream verified", "generation_id": manifest.get("generation_id"), "accounting": accounting}
