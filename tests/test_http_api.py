from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from xrecony.server import Handler, STATE


class HttpApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.source = root / "source"
        self.workspace = root / "workspace"
        self.source.mkdir()
        (self.source / "report.pdf").write_bytes(b"payload")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_dashboard_api_vertical_slice(self):
        status, initial = self.request("/api/status")
        self.assertEqual(status, 200)
        self.assertIn("progress", initial)
        status, probe = self.request("/api/source/probe", {"source": str(self.source)})
        self.assertEqual(status, 200)
        self.assertTrue(probe["ok"])
        status, accepted = self.request(
            "/api/runs/start",
            {"source": str(self.source), "workspace": str(self.workspace)},
        )
        self.assertEqual(status, 202)
        self.assertTrue(accepted["accepted"])
        deadline = time.time() + 5
        while time.time() < deadline:
            _, current = self.request("/api/status")
            if current["progress"]["state"] in {"completed", "failed"}:
                break
            time.sleep(0.02)
        self.assertEqual(current["progress"]["state"], "completed", current)
        _, records = self.request("/api/records?page_size=10")
        self.assertEqual(records["total"], 2)
        self.assertIn("facets", records)
        _, detail = self.request(f"/api/records/{records['records'][0]['id']}")
        self.assertIn("rel_path", detail)
        _, benchmark = self.request("/api/benchmark")
        self.assertFalse(benchmark["claim_eligible"])
        _, intelligence = self.request("/api/intelligence")
        self.assertIn("summary", intelligence)
        _, graph = self.request("/api/v1/graph")
        self.assertEqual(graph["header"]["node_count"], 2)
        self.assertEqual(len(graph["header"]["realities"]), 4)
        _, universe = self.request("/api/v1/universe")
        self.assertEqual(universe["topology"]["objects"], 2)
        _, events = self.request("/api/v1/events")
        self.assertEqual(events["mode"], "certified-replay")
        self.assertTrue(events["events"])
        _, connectors = self.request("/api/v1/connectors")
        self.assertEqual(connectors["connectors"][0]["state"], "operational")
        _, system = self.request("/api/system")
        self.assertIn("adapters", system)
        _, verified = self.request("/api/receipt/verify", {})
        self.assertTrue(verified["valid"], verified)


if __name__ == "__main__":
    unittest.main()
