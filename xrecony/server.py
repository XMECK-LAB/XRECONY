from __future__ import annotations

import json
import mimetypes
import os
import tempfile
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .adapters import adapter_status
from .connectors import connector_registry
from .events import read_events
from .models import ScanProgress
from .query import query_records, record_detail
from .scanner import reconstruct, source_probe
from .store import (
    activate_generation,
    active_generation_dir,
    can_rollback,
    generation_diff,
    list_generations,
    read_audit,
    rollback_generation,
)
from .verify import verify_generation


class AppState:
    def __init__(self):
        self.progress = ScanProgress()
        self.lock = threading.Lock()
        self.workspace: Path | None = None
        self.error: str | None = None
        self.cancel_event = threading.Event()


STATE = AppState()
WEB_ROOT = Path(__file__).with_name("web")


def _state_dir() -> Path:
    configured = os.environ.get("XRECONY_STATE_DIR")
    candidates = [
        Path(configured) if configured else None,
        Path(os.environ.get("LOCALAPPDATA", "")) / "XRECONY" if os.environ.get("LOCALAPPDATA") else None,
        Path(tempfile.gettempdir()) / "XRECONY",
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    raise OSError("No writable XRECONY state directory is available")


def _remember_workspace(workspace: Path) -> None:
    path = _state_dir() / "recent_workspace.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"workspace": str(workspace)}, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _load_recent_workspace() -> Path | None:
    path = _state_dir() / "recent_workspace.json"
    if not path.exists():
        return None
    try:
        workspace = Path(json.loads(path.read_text(encoding="utf-8"))["workspace"])
    except (OSError, KeyError, json.JSONDecodeError):
        return None
    return workspace if (workspace / "workspace.json").is_file() else None


def _hydrate_progress(workspace: Path) -> None:
    active = active_generation_dir(workspace)
    if not active:
        STATE.progress = ScanProgress(workspace=str(workspace))
        return
    manifest = json.loads((active / "generation.json").read_text(encoding="utf-8"))
    benchmark_path = active / "benchmark.json"
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8")) if benchmark_path.is_file() else {}
    accounting = manifest.get("accounting", {})
    capacity = manifest.get("capacity", {})
    timing = benchmark.get("timing", {})
    STATE.progress = ScanProgress(
        state="completed",
        stage="certified",
        source=manifest.get("source", ""),
        workspace=str(workspace),
        generation_id=manifest.get("generation_id", ""),
        records=accounting.get("records", 0),
        files=accounting.get("files", 0),
        directories=accounting.get("directories", 0),
        links=accounting.get("links", 0),
        errors=accounting.get("errors", 0),
        logical_bytes=capacity.get("logical_bytes", 0),
        allocated_bytes=capacity.get("allocated_bytes_observed", 0),
        adapter=benchmark.get("environment", {}).get("adapter", "python-optimized-scandir-xrf1"),
        integrity_state=manifest.get("integrity", {}).get("state", "unknown"),
        elapsed_seconds=timing.get("elapsed_seconds", manifest.get("elapsed_seconds", 0)),
        records_per_second=timing.get("records_per_second", 0),
        progress_percent=100,
        finished_utc=timing.get("finished_utc"),
        message="Certified Reconstruction Twin ready",
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "XRECONY/V4.5.1"

    def log_message(self, fmt, *args):
        return

    def _json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def _download(self, path: Path, download_name: str):
        if not path.is_file():
            return self._json({"error": "File is not available"}, 404)
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        args = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/system":
            return self._json(
                {
                    "product": "XRECONY",
                    "version": __version__,
                    "release": "V4.5.1 Windows Distribution",
                    "product_modes": ["A", "B"],
                    "product_c": "parked-absent",
                    "kernel": "python-optimized-scandir-xrf1",
                    "local_only": True,
                    "fabric": "XRF-DESKTOP-FABRIC-4.5",
                    "claim_state": "evidence-locked",
                    "adapters": adapter_status(),
                }
            )
        if parsed.path == "/api/v1/connectors":
            return self._json(connector_registry())
        if parsed.path == "/api/adapters":
            return self._json(adapter_status())
        if parsed.path == "/api/status":
            with STATE.lock:
                rollback_available = bool(STATE.workspace and can_rollback(STATE.workspace))
                payload = STATE.progress.to_dict()
                payload.update(
                    {
                        "progress": STATE.progress.to_dict(),
                        "running": STATE.progress.state == "running",
                        "last_result": STATE.progress.to_dict(),
                        "workspace": str(STATE.workspace or payload.get("workspace", "")),
                        "error": STATE.error,
                        "can_rollback": rollback_available,
                    }
                )
                return self._json(payload)
        if parsed.path == "/api/generations":
            if not STATE.workspace:
                return self._json({"generations": [], "can_rollback": False})
            return self._json(
                {
                    "generations": list_generations(STATE.workspace),
                    "can_rollback": can_rollback(STATE.workspace),
                }
            )
        if parsed.path == "/api/records":
            active = self._active_or_none()
            if not active:
                return self._json({"records": [], "total": 0, "page": 1, "page_size": 100})
            data = query_records(
                active,
                query=args.get("q", [""])[0],
                category=args.get("category", [""])[0],
                kind=args.get("kind", [""])[0],
                view=args.get("view", ["source"])[0],
                page=int(args.get("page", ["1"])[0]),
                page_size=int(args.get("page_size", ["100"])[0]),
            )
            return self._json(data)
        if parsed.path == "/api/record":
            active = self._active_or_none()
            if not active:
                return self._json({"error": "No active generation"}, 404)
            item = record_detail(active, args.get("id", [""])[0])
            return self._json(item or {"error": "Record not found"}, 200 if item else 404)
        if parsed.path.startswith("/api/records/"):
            active = self._active_or_none()
            if not active:
                return self._json({"error": "No active generation"}, 404)
            item = record_detail(active, urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1]))
            return self._json(item or {"error": "Record not found"}, 200 if item else 404)
        if parsed.path in {
            "/api/receipt", "/api/receipt/human", "/api/benchmark", "/api/intelligence",
            "/api/v1/graph", "/api/v1/universe", "/api/v1/diagnostics", "/api/v1/passport",
        }:
            active = self._active_or_none()
            if not active:
                return self._json({"error": "No active generation"}, 404)
            filename = {
                "/api/receipt": "receipt.json",
                "/api/receipt/human": "receipt_summary.json",
                "/api/benchmark": "benchmark.json",
                "/api/intelligence": "intelligence.json",
                "/api/v1/graph": "reconstruction_graph.json",
                "/api/v1/universe": "data_universe.json",
                "/api/v1/diagnostics": "diagnostics.json",
                "/api/v1/passport": "source_passport.json",
            }[parsed.path]
            return self._json(json.loads((active / filename).read_text(encoding="utf-8")))
        if parsed.path == "/api/v1/events":
            active = self._active_or_none()
            if not active:
                return self._json({"mode": "certified-replay", "events": []})
            return self._json({"mode": "certified-replay", "events": read_events(active)})
        if parsed.path in {"/api/download/receipt", "/api/download/benchmark"}:
            active = self._active_or_none()
            if not active:
                return self._json({"error": "No active generation"}, 404)
            filename = "receipt.json" if parsed.path.endswith("receipt") else "benchmark.json"
            return self._download(active / filename, f"{active.name}_{filename}")
        if parsed.path == "/api/audit":
            if not STATE.workspace:
                return self._json({"events": []})
            return self._json({"events": read_audit(STATE.workspace)})
        return self._static(parsed.path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            data = self._body()
            if parsed.path == "/api/source/probe":
                result = source_probe(data.get("source") or data["path"])
                result["ok"] = True
                return self._json(result)
            if parsed.path == "/api/dialog/folder":
                return self._json({"path": _pick_folder(data.get("title", "Select folder"))})
            if parsed.path in {"/api/workspaces/open", "/api/workspace/open"}:
                workspace = Path(data["workspace"]).expanduser().resolve()
                if not (workspace / "workspace.json").is_file():
                    raise ValueError("This folder is not an XRECONY workspace")
                STATE.workspace = workspace
                _hydrate_progress(workspace)
                _remember_workspace(workspace)
                return self._json(
                    {
                        "opened": str(workspace),
                        "generations": list_generations(workspace),
                        "can_rollback": can_rollback(workspace),
                    }
                )
            if parsed.path in {"/api/runs/start", "/api/reconstruct/start"}:
                with STATE.lock:
                    if STATE.progress.state == "running":
                        return self._json({"error": "A reconstruction is already running"}, 409)
                    STATE.progress = ScanProgress(
                        state="running",
                        stage="queued",
                        mode=data.get("mode", "normal"),
                        source=data["source"],
                        workspace=data["workspace"],
                        message="Run accepted; sealing source scope",
                        progress_percent=1,
                    )
                    STATE.workspace = Path(data["workspace"]).expanduser().resolve()
                    STATE.error = None
                    STATE.cancel_event = threading.Event()
                    _remember_workspace(STATE.workspace)
                thread = threading.Thread(
                    target=_scan_worker,
                    args=(
                        data["source"],
                        data["workspace"],
                        data.get("mode", "normal"),
                        data.get("cold_warm_declaration", "unspecified"),
                    ),
                    daemon=True,
                )
                thread.start()
                return self._json({"accepted": True}, HTTPStatus.ACCEPTED)
            if parsed.path in {"/api/runs/cancel", "/api/reconstruct/cancel"}:
                with STATE.lock:
                    if STATE.progress.state != "running":
                        raise ValueError("No reconstruction is currently running")
                    STATE.cancel_event.set()
                    STATE.progress.message = "Cancellation requested; stopping at a safe checkpoint"
                return self._json({"cancel_requested": True}, HTTPStatus.ACCEPTED)
            if parsed.path == "/api/generations/activate":
                self._require_workspace()
                activate_generation(STATE.workspace, data["generation_id"])
                return self._json({"activated": data["generation_id"]})
            if parsed.path == "/api/generations/rollback":
                self._require_workspace()
                generation_id = rollback_generation(STATE.workspace)
                return self._json({"activated": generation_id})
            if parsed.path == "/api/generations/diff":
                self._require_workspace()
                return self._json(
                    generation_diff(STATE.workspace, data["from"], data["to"])
                )
            if parsed.path in {"/api/verify", "/api/receipt/verify"}:
                active = self._active_or_error()
                return self._json(verify_generation(str(active)))
            return self._json({"error": "Not found"}, 404)
        except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def _require_workspace(self):
        if not STATE.workspace:
            raise ValueError("No workspace is open")

    def _active_or_none(self):
        return active_generation_dir(STATE.workspace) if STATE.workspace else None

    def _active_or_error(self):
        active = self._active_or_none()
        if not active:
            raise ValueError("No active generation")
        return active

    def _static(self, path):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB_ROOT / rel).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            return self._json({"error": "Not found"}, 404)
        if not target.is_file():
            target = WEB_ROOT / "index.html"
        payload = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)


def _pick_folder(title: str) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title=title, mustexist=True)
        root.destroy()
        return path
    except Exception as exc:
        raise ValueError(f"Native folder picker unavailable: {exc}") from exc


def _scan_worker(source: str, workspace: str, mode: str, cold_warm: str):
    try:
        reconstruct(
            source,
            workspace,
            STATE.progress,
            STATE.lock,
            cancel_event=STATE.cancel_event,
            mode=mode,
            cold_warm_declaration=cold_warm,
        )
    except Exception as exc:
        with STATE.lock:
            STATE.error = f"{type(exc).__name__}: {exc}"


def run_server(port: int = 8765, open_browser: bool = False):
    recent = _load_recent_workspace()
    if recent:
        STATE.workspace = recent
        _hydrate_progress(recent)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"XRECONY Reconstruction Fabric One running at {url}")
    print("Press Ctrl+C to stop. Product A+B only; Product C is parked and absent.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server(open_browser=True)
