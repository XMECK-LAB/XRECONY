from __future__ import annotations

import hashlib
import json
import os
import platform
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .categories import classify
from .events import emit_event
from .fabric import build_fabric
from .intelligence import write_intelligence
from .models import ScanProgress, ScopeSeal, normalize_path
from .passport import build_source_passport
from .store import GenerationStore, activate_generation, append_audit, ensure_workspace


class ScanCancelled(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(source_identity: str, rel_path: str) -> str:
    raw = f"{source_identity}\0{rel_path}".encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(raw).hexdigest()[:32]


def source_identity(path: Path) -> str:
    stat = path.stat()
    raw = f"{path}\0{getattr(stat, 'st_dev', 0)}\0{getattr(stat, 'st_ino', 0)}"
    return hashlib.sha256(raw.encode("utf-8", errors="surrogatepass")).hexdigest()


def source_probe(path_text: str) -> dict:
    path = Path(normalize_path(path_text))
    if not path.exists() or not path.is_dir():
        raise ValueError("Source must be an existing folder")
    stat = path.stat()
    try:
        import shutil

        usage = shutil.disk_usage(path)
        capacity = {"total": usage.total, "used": usage.used, "free": usage.free}
    except OSError:
        capacity = {"total": None, "used": None, "free": None}
    return {
        "path": str(path),
        "name": path.name or str(path),
        "identity": source_identity(path),
        "platform": platform.system(),
        "device": getattr(stat, "st_dev", None),
        "readable": os.access(path, os.R_OK),
        "writable": os.access(path, os.W_OK),
        "capacity": capacity,
        "adapter": "python-optimized-scandir-xrf1",
        "evidence_depth": "D0/D1",
    }


def validate_scope(source: Path, workspace: Path) -> None:
    if not source.exists() or not source.is_dir():
        raise ValueError("Source must be an existing folder")
    if source == workspace or source in workspace.parents or workspace in source.parents:
        raise ValueError("Workspace and source must be separate; neither may contain the other")


def reconstruct(
    source_text: str,
    workspace_text: str,
    progress: ScanProgress | None = None,
    progress_lock: threading.Lock | None = None,
    on_update: Callable[[ScanProgress], None] | None = None,
    cancel_event: threading.Event | None = None,
    mode: str = "normal",
    cold_warm_declaration: str = "unspecified",
) -> dict:
    source = Path(normalize_path(source_text))
    workspace = Path(normalize_path(workspace_text))
    validate_scope(source, workspace)
    ensure_workspace(workspace)
    identity = source_identity(source)
    generation_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    generation_dir = workspace / "generations" / generation_id
    seal = ScopeSeal(str(source), str(workspace), identity, utc_now())
    started = time.perf_counter()
    p = progress or ScanProgress()
    cancel_event = cancel_event or threading.Event()

    def update(**values):
        if progress_lock:
            progress_lock.acquire()
        try:
            for key, value in values.items():
                setattr(p, key, value)
            p.elapsed_seconds = round(time.perf_counter() - started, 4)
            p.records_per_second = round(p.records / p.elapsed_seconds, 2) if p.elapsed_seconds else 0.0
            if on_update:
                on_update(p)
        finally:
            if progress_lock:
                progress_lock.release()

    update(
        state="running",
        stage="scope-sealed",
        source=str(source),
        workspace=str(workspace),
        generation_id=generation_id,
        started_utc=utc_now(),
        mode=mode,
        message="Scope sealed",
        progress_percent=8,
    )
    store = None
    totals = {
        "records": 0,
        "files": 0,
        "directories": 0,
        "links": 0,
        "errors": 0,
        "metadata_bytes": 0,
        "logical_bytes": 0,
        "allocated_bytes": 0,
    }
    stage_times: dict[str, float] = {}

    def stage(name: str, message: str):
        stage_times[name] = round(time.perf_counter() - started, 4)
        update(stage=name, message=message)

    try:
        store = GenerationStore(generation_dir)
        passport = build_source_passport(source, identity)
        (generation_dir / "source_passport.json").write_text(
            json.dumps(passport, indent=2, sort_keys=True), encoding="utf-8"
        )
        emit_event(generation_dir, "scope.sealed", {"source_identity": identity})
        (generation_dir / "scope.json").write_text(
            json.dumps(seal.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        stage("enumerating", "Enumerating source metadata")
        emit_event(generation_dir, "capture.started", {"evidence_depth": "D0/D1"})
        update(progress_percent=24)
        root_id = stable_id(identity, ".")
        root_stat = source.stat()
        root_year = str(datetime.fromtimestamp(root_stat.st_mtime, tz=timezone.utc).year)
        root_row = (
            root_id,
            None,
            source.name or str(source),
            ".",
            str(source),
            "directory",
            0,
            getattr(root_stat, "st_mtime_ns", None),
            getattr(root_stat, "st_ctime_ns", None),
            "",
            "folders",
            root_year,
            "placed",
            "",
            f"Folders/{source.name}",
            f"{root_year}/{source.name}",
        )
        store.insert_many([root_row])
        totals["records"] = 1
        totals["directories"] = 1
        stack: list[tuple[Path, str, str]] = [(source, ".", root_id)]
        batch: list[tuple] = []
        while stack:
            if cancel_event.is_set():
                raise ScanCancelled("Reconstruction cancelled by the operator")
            folder, folder_rel, parent_record_id = stack.pop()
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        if cancel_event.is_set():
                            raise ScanCancelled("Reconstruction cancelled by the operator")
                        rel = entry.name if folder_rel == "." else f"{folder_rel}/{entry.name}"
                        rid = stable_id(identity, rel)
                        try:
                            is_link = entry.is_symlink()
                            is_dir = entry.is_dir(follow_symlinks=False)
                            stat = entry.stat(follow_symlinks=False)
                            kind = "link" if is_link else ("directory" if is_dir else "file")
                            category, ext = classify(entry.name, is_dir)
                            year = (
                                str(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).year)
                                if stat.st_mtime
                                else "Unknown"
                            )
                            size = 0 if is_dir else int(stat.st_size)
                            allocated = 0 if is_dir else int(getattr(stat, "st_blocks", 0) * 512 or size)
                            type_path = f"{category.title()}/{entry.name}"
                            time_path = f"{year}/{category.title()}/{entry.name}"
                            row = (
                                rid,
                                parent_record_id,
                                entry.name,
                                rel,
                                entry.path,
                                kind,
                                size,
                                getattr(stat, "st_mtime_ns", None),
                                getattr(stat, "st_ctime_ns", None),
                                ext,
                                category,
                                year,
                                "placed",
                                "",
                                type_path,
                                time_path,
                            )
                            totals[
                                "files" if kind == "file" else "links" if kind == "link" else "directories"
                            ] += 1
                            totals["metadata_bytes"] += len(rel.encode("utf-8", errors="replace")) + 128
                            totals["logical_bytes"] += size
                            totals["allocated_bytes"] += allocated
                            if is_dir and not is_link:
                                stack.append((Path(entry.path), rel, rid))
                        except OSError as exc:
                            category, ext = classify(entry.name, False)
                            row = (
                                rid,
                                parent_record_id,
                                entry.name,
                                rel,
                                entry.path,
                                "unknown",
                                0,
                                None,
                                None,
                                ext,
                                category,
                                "Unknown",
                                "error",
                                f"{type(exc).__name__}: {exc}",
                                f"Errors/{entry.name}",
                                f"Unknown/Errors/{entry.name}",
                            )
                            totals["errors"] += 1
                        batch.append(row)
                        totals["records"] += 1
                        if len(batch) >= 2000:
                            store.insert_many(batch)
                            store.commit()
                            batch.clear()
                            checkpoint = {
                                "format": "xrecony-capture-checkpoint-v1",
                                "generation_id": generation_id,
                                "source_identity": identity,
                                "records_committed": totals["records"],
                                "pending_directories": len(stack),
                                "last_relative_folder": folder_rel,
                                "resumability": "recovery checkpoint; exact mid-directory replay may repeat enumeration",
                                "source_mutation_performed": False,
                            }
                            (generation_dir / "checkpoint.json").write_text(
                                json.dumps(checkpoint, indent=2, sort_keys=True), encoding="utf-8"
                            )
                            emit_event(
                                generation_dir,
                                "capture.checkpoint",
                                {"records": totals["records"], "pending_directories": len(stack)},
                            )
                            update(**totals, progress_percent=38, message=f"Indexed {totals['records']:,} records")
            except ScanCancelled:
                raise
            except OSError as exc:
                error_rel = f"{folder_rel}/<access-error>"
                rid = stable_id(identity, error_rel)
                batch.append(
                    (
                        rid,
                        parent_record_id,
                        "<access-error>",
                        error_rel,
                        str(folder),
                        "unknown",
                        0,
                        None,
                        None,
                        "",
                        "other",
                        "Unknown",
                        "error",
                        f"{type(exc).__name__}: {exc}",
                        "Errors/Access",
                        "Unknown/Errors/Access",
                    )
                )
                totals["records"] += 1
                totals["errors"] += 1
        if batch:
            store.insert_many(batch)
        store.commit()
        stage("accounting", "Reconciling complete object accounting")
        emit_event(generation_dir, "capture.completed", {"records": totals["records"]})
        update(progress_percent=62)
        accounting = _account_and_hash(store.conn)
        if accounting["records"] != totals["records"]:
            raise RuntimeError("Accounting mismatch: discovered records do not equal stored records")
        stage("integrity", "Verifying source metadata stability")
        emit_event(generation_dir, "accounting.verified", {"records": accounting["records"]})
        update(progress_percent=78)
        integrity = _verify_live_source(store.conn)
        update(integrity_state="verified" if integrity["changed"] == 0 else "drift-detected")
        stage("preparing-fabric", "Preparing reconstruction intelligence")
        update(progress_percent=84)
        stream_hash = accounting.pop("record_stream_sha256")
        receipt = {
            "format": "xrecony-reconstruction-receipt-xrf-one-v1",
            "generation_id": generation_id,
            "created_utc": utc_now(),
            "scope": seal.to_dict(),
            "accounting": accounting,
            "capacity": {
                "logical_bytes": totals["logical_bytes"],
                "allocated_bytes_observed": totals["allocated_bytes"],
                "metadata_bytes_estimated": totals["metadata_bytes"],
            },
            "views": ["source", "type", "timeline", "recovery"],
            "record_stream_sha256": stream_hash,
            "source_integrity": integrity,
            "source_mutation_performed": False,
            "kernel": "python-optimized-scandir-xrf1",
            "source_passport_sha256": hashlib.sha256(
                (generation_dir / "source_passport.json").read_bytes()
            ).hexdigest(),
            "claim_boundary": "Not a native-NTFS, fastest, world-record, or production result",
        }
        finished_utc = utc_now()
        elapsed = round(time.perf_counter() - started, 4)
        benchmark = {
            "format": "xrecony-benchmark-report-xrf-one-v1",
            "mode": mode,
            "cold_warm_declaration": cold_warm_declaration,
            "claim_eligible": False,
            "generation_id": generation_id,
            "source": {
                "path": str(source),
                "identity": identity,
                "logical_bytes": totals["logical_bytes"],
                "records": accounting["records"],
                "files": accounting["files"],
                "directories": accounting["directories"],
            },
            "environment": {
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "processor": platform.processor(),
                "adapter": "python-optimized-scandir-xrf1",
            },
            "timing": {
                "started_utc": p.started_utc,
                "finished_utc": finished_utc,
                "elapsed_seconds": elapsed,
                "stage_offsets_seconds": stage_times,
                "records_per_second": round(accounting["records"] / elapsed, 2) if elapsed else 0,
            },
            "accounting": accounting,
            "integrity": integrity,
            "claim_boundary": receipt["claim_boundary"],
        }
        intelligence = write_intelligence(generation_dir)

        def fabric_progress(part: str, completed: int, total: int) -> None:
            ratio = completed / total if total else 1.0
            if part == "nodes":
                percent = 86 + ratio * 6
                message = f"Compiling CRG objects — {completed:,}/{total:,}"
            elif part == "families":
                percent = 92 + ratio * 3
                message = f"Linking version families — {completed:,}/{total:,}"
            elif part == "duplicates":
                percent = 95 + ratio * 3
                message = f"Linking duplicate candidates — {completed:,}/{total:,}"
            else:
                percent = 98
                message = "Reconstruction Fabric compiled"
            update(stage="compiling-fabric", message=message, progress_percent=round(percent, 2))

        stage("compiling-fabric", "Compiling streamed Counterfactual Reconstruction Graph")
        emit_event(generation_dir, "fabric.started", {"records": accounting["records"]})
        try:
            fabric = build_fabric(
                generation_dir,
                identity,
                cancel_event=cancel_event,
                on_progress=fabric_progress,
            )
        except InterruptedError as exc:
            raise ScanCancelled(str(exc)) from exc
        stage("certifying", "Certifying Reconstruction Fabric")
        update(progress_percent=99)
        receipt["fabric"] = {
            "graph_sha256": fabric["graph"]["graph_sha256"],
            "nodes": fabric["graph"]["node_count"],
            "relationships": fabric["graph"]["relationship_count"],
            "realities": fabric["graph"]["realities"],
        }
        receipt_bytes = json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8")
        (generation_dir / "receipt.json").write_bytes(receipt_bytes)
        receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
        finished_utc = utc_now()
        elapsed = round(time.perf_counter() - started, 4)
        benchmark["timing"]["finished_utc"] = finished_utc
        benchmark["timing"]["elapsed_seconds"] = elapsed
        benchmark["timing"]["stage_offsets_seconds"] = stage_times
        benchmark["timing"]["records_per_second"] = (
            round(accounting["records"] / elapsed, 2) if elapsed else 0
        )
        (generation_dir / "benchmark.json").write_text(
            json.dumps(benchmark, indent=2, sort_keys=True), encoding="utf-8"
        )
        emit_event(
            generation_dir,
            "fabric.compiled",
            {"nodes": fabric["graph"]["node_count"], "relationships": fabric["graph"]["relationship_count"]},
        )
        human = _human_receipt(receipt, benchmark)
        (generation_dir / "receipt_summary.json").write_text(
            json.dumps(human, indent=2, sort_keys=True), encoding="utf-8"
        )
        manifest = {
            "format": "xrecony-generation-xrf-one-v1",
            "generation_id": generation_id,
            "created_utc": receipt["created_utc"],
            "source": str(source),
            "source_identity": identity,
            "state": "certified",
            "accounting": accounting,
            "capacity": receipt["capacity"],
            "integrity": integrity,
            "receipt_sha256": receipt_sha,
            "available_views": receipt["views"],
            "intelligence_summary": intelligence["summary"],
            "fabric_summary": fabric["graph"],
            "elapsed_seconds": elapsed,
        }
        (generation_dir / "generation.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        store.close()
        store = None
        activate_generation(workspace, generation_id)
        emit_event(generation_dir, "generation.certified", {"receipt_sha256": receipt_sha})
        append_audit(
            workspace,
            "generation_certified",
            {
                "generation_id": generation_id,
                "records": accounting["records"],
                "logical_bytes": totals["logical_bytes"],
                "integrity": integrity["state"],
            },
        )
        update(
            state="completed",
            stage="certified",
            **totals,
            finished_utc=finished_utc,
            message="Certified Reconstruction Twin ready",
            progress_percent=100,
        )
        return {
            "generation": manifest,
            "receipt": receipt,
            "human_receipt": human,
            "benchmark": benchmark,
            "intelligence": intelligence,
            "progress": p.to_dict(),
        }
    except ScanCancelled as exc:
        if store is not None:
            store.close()
            store = None
        incomplete = {
            "format": "xrecony-generation-xrf-one-v1",
            "generation_id": generation_id,
            "created_utc": utc_now(),
            "source": str(source),
            "state": "cancelled-incomplete",
            "accounting": totals,
            "reason": str(exc),
        }
        (generation_dir / "incomplete_generation.json").write_text(
            json.dumps(incomplete, indent=2, sort_keys=True), encoding="utf-8"
        )
        append_audit(workspace, "run_cancelled", {"generation_id": generation_id, "records": totals["records"]})
        update(state="cancelled", stage="cancelled", finished_utc=utc_now(), message=str(exc))
        return {"generation": incomplete, "progress": p.to_dict()}
    except Exception as exc:
        if store is not None:
            store.close()
        append_audit(
            workspace,
            "run_failed",
            {"generation_id": generation_id, "error": f"{type(exc).__name__}: {exc}"},
        )
        update(
            state="failed",
            stage="failed",
            finished_utc=utc_now(),
            message=f"{type(exc).__name__}: {exc}",
        )
        raise


def _account_and_hash(conn: sqlite3.Connection) -> dict:
    counts = {row[0]: row[1] for row in conn.execute("SELECT status, COUNT(*) FROM records GROUP BY status")}
    kinds = {row[0]: row[1] for row in conn.execute("SELECT kind, COUNT(*) FROM records GROUP BY kind")}
    total = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    digest = hashlib.sha256()
    for row in conn.execute(
        "SELECT record_id,parent_id,name,rel_path,kind,size,mtime_ns,extension,category,year,status,error "
        "FROM records ORDER BY rel_path COLLATE BINARY"
    ):
        digest.update(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8", errors="surrogatepass"
            )
        )
        digest.update(b"\n")
    return {
        "records": total,
        "placed": counts.get("placed", 0),
        "unresolved": counts.get("unresolved", 0),
        "excluded": counts.get("excluded", 0),
        "errors": counts.get("error", 0),
        "quarantined": counts.get("quarantined", 0),
        "files": kinds.get("file", 0),
        "directories": kinds.get("directory", 0),
        "links": kinds.get("link", 0),
        "unknown": kinds.get("unknown", 0),
        "record_stream_sha256": digest.hexdigest(),
    }


def _verify_live_source(conn: sqlite3.Connection) -> dict:
    digest = hashlib.sha256()
    checked = changed = missing = inaccessible = 0
    for rel_path, abs_path, kind, size, mtime_ns, status in conn.execute(
        "SELECT rel_path,abs_path,kind,size,mtime_ns,status FROM records ORDER BY rel_path COLLATE BINARY"
    ):
        if status != "placed":
            continue
        try:
            stat = os.stat(abs_path, follow_symlinks=False)
            live_size = 0 if kind == "directory" else int(stat.st_size)
            live_mtime = getattr(stat, "st_mtime_ns", None)
            checked += 1
            if live_size != size or live_mtime != mtime_ns:
                changed += 1
            digest.update(
                json.dumps((rel_path, kind, live_size, live_mtime), separators=(",", ":")).encode(
                    "utf-8", errors="surrogatepass"
                )
            )
            digest.update(b"\n")
        except FileNotFoundError:
            missing += 1
        except OSError:
            inaccessible += 1
    state = "stable" if not (changed or missing or inaccessible) else "drift-detected"
    return {
        "state": state,
        "checked": checked,
        "changed": changed,
        "missing": missing,
        "inaccessible": inaccessible,
        "live_manifest_sha256": digest.hexdigest(),
        "meaning": "Observed source metadata stability during this run; not a proof of disk-level immutability",
    }


def _human_receipt(receipt: dict, benchmark: dict) -> dict:
    accounting = receipt["accounting"]
    terminal = sum(
        accounting.get(key, 0)
        for key in ("placed", "unresolved", "excluded", "errors", "quarantined")
    )
    return {
        "title": "XRECONY Reconstruction Receipt",
        "generation_id": receipt["generation_id"],
        "verified_accounting": terminal == accounting["records"],
        "accounting_equation": (
            f"{accounting['records']} discovered = {accounting['placed']} placed + "
            f"{accounting['unresolved']} unresolved + {accounting['excluded']} excluded + "
            f"{accounting['errors']} errors + {accounting['quarantined']} quarantined"
        ),
        "source": receipt["scope"]["source"],
        "evidence_depth": receipt["scope"]["evidence_depth"],
        "records": accounting["records"],
        "logical_bytes": receipt["capacity"]["logical_bytes"],
        "source_integrity": receipt["source_integrity"],
        "source_mutation_performed": False,
        "receipt_verification": "Use the independent verifier; UI status is not the authority",
        "elapsed_seconds": benchmark["timing"]["elapsed_seconds"],
        "adapter": receipt["kernel"],
        "claim_boundary": receipt["claim_boundary"],
    }
