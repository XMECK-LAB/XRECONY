from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from xrecony.fixtures import build_scale_fixture
from xrecony.intelligence import build_intelligence
from xrecony.benchmark_suite import run_suite
from xrecony.scanner import reconstruct
from xrecony.store import active_generation_dir, can_rollback, generation_diff, list_generations, rollback_generation
from xrecony.verify import verify_generation
from xrecony.connectors import connector_registry
from xrecony.events import read_events
from xrecony.fabric import build_fabric
from xrecony.passport import verify_source_passport


def digest_tree(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.source = base / "source"
        self.workspace = base / "workspace"
        (self.source / "School" / "Photos").mkdir(parents=True)
        (self.source / "Work").mkdir()
        (self.source / "School" / "resume_2009.docx").write_bytes(b"old resume")
        (self.source / "School" / "Photos" / "pic.jpg").write_bytes(b"image payload")
        (self.source / "Work" / "resume_2026.pdf").write_bytes(b"new resume")

    def tearDown(self):
        self.temp.cleanup()

    def test_reconstruction_is_read_only_and_verifiable(self):
        before = digest_tree(self.source)
        result = reconstruct(str(self.source), str(self.workspace))
        after = digest_tree(self.source)
        self.assertEqual(before, after)
        self.assertEqual(result["receipt"]["accounting"]["records"], 7)
        active = active_generation_dir(self.workspace)
        verification = verify_generation(str(active))
        self.assertTrue(verification["valid"], verification)
        self.assertEqual(result["receipt"]["source_integrity"]["state"], "stable")
        self.assertFalse(result["benchmark"]["claim_eligible"])
        for filename in ("receipt.json", "receipt_summary.json", "benchmark.json", "generation.json"):
            self.assertTrue((active / filename).is_file(), filename)
        for filename in (
            "source_passport.json", "reconstruction_graph.json", "data_universe.json",
            "diagnostics.json", "events.jsonl",
        ):
            self.assertTrue((active / filename).is_file(), filename)
        intelligence = build_intelligence(active)
        self.assertIn("duplicate_candidate_groups", intelligence["summary"])

    def test_generations_and_rollback(self):
        first = reconstruct(str(self.source), str(self.workspace))["generation"]["generation_id"]
        self.assertFalse(can_rollback(self.workspace))
        (self.source / "new.txt").write_text("new", encoding="utf-8")
        second = reconstruct(str(self.source), str(self.workspace))["generation"]["generation_id"]
        self.assertNotEqual(first, second)
        generations = list_generations(self.workspace)
        self.assertEqual(len(generations), 2)
        self.assertTrue(can_rollback(self.workspace))
        diff = generation_diff(self.workspace, first, second)
        self.assertEqual(diff["counts"]["added"], 1)
        self.assertIn("new.txt", diff["added"])
        self.assertIsInstance(diff["changed"], list)
        rolled = rollback_generation(self.workspace)
        self.assertEqual(rolled, first)
        self.assertEqual(active_generation_dir(self.workspace).name, first)

    def test_receipt_tampering_is_detected(self):
        reconstruct(str(self.source), str(self.workspace))
        active = active_generation_dir(self.workspace)
        receipt = json.loads((active / "receipt.json").read_text(encoding="utf-8"))
        receipt["accounting"]["files"] = 999
        (active / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        self.assertFalse(verify_generation(str(active))["valid"])

    def test_workspace_cannot_be_inside_source(self):
        with self.assertRaises(ValueError):
            reconstruct(str(self.source), str(self.source / "workspace"))

    def test_pre_cancelled_run_is_incomplete_and_not_activated(self):
        cancel = threading.Event()
        cancel.set()
        result = reconstruct(str(self.source), str(self.workspace), cancel_event=cancel)
        self.assertEqual(result["generation"]["state"], "cancelled-incomplete")
        self.assertIsNone(active_generation_dir(self.workspace))
        generation = self.workspace / "generations" / result["generation"]["generation_id"]
        self.assertTrue((generation / "incomplete_generation.json").is_file())
        self.assertFalse((generation / "generation.json").exists())

    def test_scale_fixture_is_deterministic_and_refuses_overwrite(self):
        target = Path(self.temp.name) / "fixture"
        result = build_scale_fixture(str(target), records=12)
        self.assertEqual(result["records_requested"], 12)
        self.assertEqual(len(list(target.rglob("xrecony-fixture-*"))), 12)
        with self.assertRaises(ValueError):
            build_scale_fixture(str(target), records=1)

    def test_generation_diff_explains_changed_fields(self):
        first = reconstruct(str(self.source), str(self.workspace))["generation"]["generation_id"]
        target = self.source / "Work" / "resume_2026.pdf"
        target.write_bytes(b"new and larger resume")
        second = reconstruct(str(self.source), str(self.workspace))["generation"]["generation_id"]
        diff = generation_diff(self.workspace, first, second)
        item = next(item for item in diff["changed"] if item["path"] == "Work/resume_2026.pdf")
        self.assertIn("size", item["fields"])
        self.assertEqual(item["fields"]["size"]["before"], len(b"new resume"))
        self.assertEqual(item["fields"]["size"]["after"], len(b"new and larger resume"))

    def test_controlled_benchmark_suite_aggregates_three_runs(self):
        target = Path(self.temp.name) / "benchmark-suite"
        report = run_suite(str(self.source), str(target), runs=3, cache="warm")
        self.assertEqual(report["runs"], 3)
        self.assertEqual(report["cache_declaration"], "warm")
        self.assertEqual(len(report["samples"]), 3)
        self.assertFalse(report["claim_eligible"])
        self.assertTrue((target / "XRECONY_BENCHMARK_SUITE.json").is_file())

    def test_counterfactual_graph_has_four_explainable_realities(self):
        result = reconstruct(str(self.source), str(self.workspace))
        active = active_generation_dir(self.workspace)
        graph = json.loads((active / "reconstruction_graph.json").read_text(encoding="utf-8"))
        self.assertEqual(graph["header"]["node_count"], result["receipt"]["accounting"]["records"])
        self.assertEqual(graph["header"]["realities"], ["source", "type", "timeline", "recovery"])
        nodes = [
            json.loads(line)
            for line in (active / graph["node_stream"]).read_text(encoding="utf-8").splitlines()
        ]
        node = next(item for item in nodes if item["observed"]["name"] == "resume_2026.pdf")
        self.assertFalse(node["placement"]["content_read"])
        self.assertEqual(set(node["reconstructed_realities"]), {"source", "type", "timeline", "recovery"})
        self.assertGreaterEqual(len(node["placement"]["evidence"]), 3)
        self.assertTrue(verify_generation(str(active))["valid"])
        self.assertNotIn(b"\r\n", (active / graph["node_stream"]).read_bytes())
        self.assertNotIn(b"\r\n", (active / graph["relationship_stream"]).read_bytes())

    def test_source_passport_and_certified_event_replay(self):
        reconstruct(str(self.source), str(self.workspace))
        active = active_generation_dir(self.workspace)
        passport = json.loads((active / "source_passport.json").read_text(encoding="utf-8"))
        self.assertTrue(verify_source_passport(passport, self.source)["matched"])
        event_names = [item["sequence_event"] for item in read_events(active)]
        self.assertIn("scope.sealed", event_names)
        self.assertIn("fabric.compiled", event_names)
        self.assertIn("generation.certified", event_names)

    def test_connector_registry_separates_operational_from_contract_only(self):
        registry = connector_registry()
        states = {item["connector_id"]: item["state"] for item in registry["connectors"]}
        self.assertEqual(states["filesystem"], "operational")
        self.assertEqual(states["gdrive"], "contract-only")
        self.assertFalse(registry["sdk_contract"]["source_mutation_allowed"])

    def test_fabric_compilation_honors_cancellation(self):
        reconstruct(str(self.source), str(self.workspace))
        active = active_generation_dir(self.workspace)
        manifest = json.loads((active / "generation.json").read_text(encoding="utf-8"))
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(InterruptedError):
            build_fabric(
                active,
                manifest["source_identity"],
                cancel_event=cancel,
            )


if __name__ == "__main__":
    unittest.main()
