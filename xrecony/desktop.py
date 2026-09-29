from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from .server import run_server


def _wait_for_server(host: str, port: int, timeout: float = 20.0) -> None:
    """Wait for a real API response, not merely an open TCP socket."""
    deadline = time.monotonic() + timeout
    health_url = f"http://{host}:{port}/api/status"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=0.6) as response:
                if response.status == 200 and response.read(1):
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.12)
    raise RuntimeError("XRECONY could not start its local service")


def _edge_candidates() -> list[Path]:
    candidates: list[Path] = []
    discovered = shutil.which("msedge")
    if discovered:
        candidates.append(Path(discovered))
    for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    return candidates


def _edge_profile() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    profile = Path(base) / "XRECONY" / "SurfaceStudioEdge"
    profile.mkdir(parents=True, exist_ok=True)
    return profile


def _launch_edge_app(url: str) -> subprocess.Popen | None:
    for candidate in _edge_candidates():
        if not candidate.is_file():
            continue
        return subprocess.Popen(
            [
                str(candidate),
                f"--app={url}",
                f"--user-data-dir={_edge_profile()}",
                "--start-maximized",
                "--disable-features=msEdgeSidebarV2",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
            ]
        )
    return None


def _show_startup_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("XRECONY could not start", message)
        root.destroy()
    except Exception:
        pass


def run_desktop(port: int = 8765, *, force_browser: bool = False) -> None:
    """Launch a dependency-free Windows app window with a browser fallback."""
    server_thread = threading.Thread(
        target=run_server,
        kwargs={"port": port, "open_browser": False},
        name="xrecony-local-service",
        daemon=True,
    )
    server_thread.start()
    try:
        _wait_for_server("127.0.0.1", port)
    except RuntimeError as exc:
        _show_startup_error(f"{exc}\n\nClose XRECONY and start it again.")
        raise
    url = f"http://127.0.0.1:{port}/?desktop=1&surface=1.2"

    if force_browser or os.environ.get("XRECONY_DESKTOP_SHELL") == "browser":
        webbrowser.open(url)
        server_thread.join()
        return

    edge_process = _launch_edge_app(url)
    if edge_process is None:
        webbrowser.open(url)
        server_thread.join()
        return

    # The dedicated Edge profile keeps this process attached to its app window.
    # Waiting here also keeps the local API alive for the complete UI session.
    edge_process.wait()
