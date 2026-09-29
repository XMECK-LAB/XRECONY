from __future__ import annotations

import unittest
from pathlib import Path


class SurfaceContractTests(unittest.TestCase):
    def test_adaptive_breakpoints_and_no_fixed_body_floor(self):
        css = (Path(__file__).parents[1] / "xrecony" / "web" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 1100px)", css)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn("overflow-x: hidden", css)
        self.assertNotIn("min-width: 1120px", css)

    def test_all_proof_planes_exist(self):
        html = (Path(__file__).parents[1] / "xrecony" / "web" / "index.html").read_text(encoding="utf-8")
        for panel in ("command", "twin", "evolution", "proof", "benchmark", "insights", "fabric"):
            self.assertIn(f'data-panel="{panel}"', html)
        for marker in ("Structural map", "Structure layers", "Available data connections", "Data universe"):
            self.assertIn(marker, html)

    def test_v12_desktop_and_truthful_visual_contract(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "xrecony" / "web" / "index.html").read_text(encoding="utf-8")
        js = (root / "xrecony" / "web" / "app.js").read_text(encoding="utf-8")
        css = (root / "xrecony" / "web" / "styles.css").read_text(encoding="utf-8")
        launcher = (root / "xrecony" / "desktop.py").read_text(encoding="utf-8")
        self.assertIn('id="flowEngine"', html)
        self.assertIn("updateFlow(s, terminalState)", js)
        self.assertIn(".flow-engine.running", css)
        self.assertIn("--start-maximized", launcher)
        self.assertNotIn("--window-size=", launcher)
        self.assertIn("--app=", launcher)
        self.assertIn("--user-data-dir=", launcher)
        self.assertIn("/api/status", launcher)
        self.assertIn("surface=1.2", launcher)
        self.assertNotIn("import webview", launcher)
        self.assertNotIn("pythonnet", launcher)

    def test_v12_build_has_no_pythonnet_dependency(self):
        root = Path(__file__).resolve().parents[1]
        builder = (root / "BUILD_WINDOWS_EXE.bat").read_text(encoding="utf-8")
        self.assertIn("py -3.12", builder)
        self.assertIn(".build-venv", builder)
        self.assertIn("XRECONY_SURFACE_STUDIO_1_2.exe", builder)
        self.assertNotIn("pip install --upgrade pyinstaller pywebview", builder.lower())
        self.assertNotIn("--collect-all webview", builder.lower())

    def test_surface_studio_is_ui_only_and_public_facing(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "xrecony" / "web" / "index.html").read_text(encoding="utf-8")
        css = (root / "xrecony" / "web" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("SURFACE 1.2", html)
        self.assertIn("Reconstruct your data", html)
        self.assertIn("Data map", html)
        self.assertIn("Surface Studio 1.2", css)
        self.assertIn('id="startupGate"', html)
        self.assertIn('id="retryConnection"', html)
        self.assertIn('class="system-dock"', html)
        self.assertIn("connectionState(\"connecting\")", (root / "xrecony" / "web" / "app.js").read_text(encoding="utf-8"))
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertNotIn("Claim lock active", html)
        self.assertNotIn("Cortex Orb", html)

    def test_surface_v12_neural_console_and_fit_contract(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "xrecony" / "web" / "index.html").read_text(encoding="utf-8")
        js = (root / "xrecony" / "web" / "app.js").read_text(encoding="utf-8")
        css = (root / "xrecony" / "web" / "styles.css").read_text(encoding="utf-8")
        for marker in ("source-stack", "neural-rail rail-in", "neural-rail rail-out", "reality-stack", "flowProtocol", "flowPercent"):
            self.assertIn(marker, html)
        self.assertIn("STATE://CERTIFIED", js)
        self.assertIn("@media (min-width:1101px) and (max-height:900px)", css)
        self.assertIn("height:calc(100vh - 122px)", css)
        self.assertIn("@keyframes packetIn", css)
        self.assertIn("@keyframes fieldSweep", css)


if __name__ == "__main__":
    unittest.main()
