"""Test the adjudication workflow with fabricated runs in temporary folders."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.adjudicate import prepare, report
from evaluation.fixture_router import digest
from evaluation.run import read_jsonl, write_json, write_jsonl
from evaluation.runtime import PROJECT


class AdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.run, self.packets = root / "fabricated-run", root / "packets"
        self.run.mkdir()
        self.labels_path = PROJECT / "evaluation/data/labels.jsonl"
        all_labels = read_jsonl(self.labels_path)
        self.label = next(row for row in all_labels if row["issues"])
        self.case_id = self.label["case_id"]
        row = next(row for row in read_jsonl(PROJECT / "evaluation/data/inputs.jsonl")
                   if row["case_id"] == self.case_id)
        write_jsonl(self.run / "inputs.jsonl", [row])
        write_json(self.run / "manifest.json", {"backend": "live", "input_sha256": digest([row]),
                    "settings": {"systems": ["baseline", "agent"], "repeats": 1}})
        results = []
        for system in ("baseline", "agent"):
            raw = self.run / system / "repeat-1" / self.case_id
            raw.mkdir(parents=True)
            write_json(raw / "raw.json", {"final_response": "fabricated test finding"})
            results.append({"system": system, "repeat": 1, "case_id": self.case_id, "status": "ok",
                "findings": [{"finding_id": "f1", "file": "module.py",
                              "line": self.label["issues"][0]["line_start"], "description": "Test claim"}],
                "metrics": {"duration_ms": 100, "input_tokens": 20, "output_tokens": 5, "tool_errors": 0}})
        write_jsonl(self.run / "results.jsonl", results)

    def prepare(self):
        return prepare(self.run, self.labels_path, self.packets)

    def complete_packets(self):
        for path in self.packets.glob("review-*.json"):
            packet = json.loads(path.read_text())
            packet["normalization_reviewed"] = True
            for decision in packet["decisions"]:
                decision.update(gold_issue_id=self.label["issues"][0]["issue_id"], rationale="Unit test semantic match")
            write_json(path, packet)

    def test_preparation_does_not_auto_judge(self):
        self.assertEqual(self.prepare(), 2)
        with self.assertRaisesRegex(ValueError, "pending"):
            report(self.packets)

    def test_completed_judgments_score_each_system(self):
        self.prepare()
        self.complete_packets()
        output = report(self.packets)
        for name in ("baseline", "agent"):
            self.assertEqual(output["systems"][name]["repeat-1"]["quality"]["recall"], 1)

    def test_scripted_run_cannot_be_presented_as_model_evaluation(self):
        manifest = json.loads((self.run / "manifest.json").read_text())
        manifest["backend"] = "scripted"
        write_json(self.run / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "Scripted"):
            self.prepare()

    def test_incomplete_run_rejected(self):
        write_jsonl(self.run / "results.jsonl", read_jsonl(self.run / "results.jsonl")[:1])
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.prepare()

    def test_changed_gold_rejected(self):
        self.prepare()
        self.complete_packets()
        labels = read_jsonl(self.packets / "labels.snapshot.jsonl")
        labels[0]["issues"] = []
        write_jsonl(self.packets / "labels.snapshot.jsonl", labels)
        with self.assertRaisesRegex(ValueError, "Gold labels changed"):
            report(self.packets)

    def test_report_preserves_provisional_assistant_provenance(self):
        self.prepare()
        self.complete_packets()
        mapping = json.loads((self.packets / "mapping.json").read_text())
        mapping["adjudication"] = {"reviewer_type": "assistant", "human_validated": False}
        write_json(self.packets / "mapping.json", mapping)
        self.assertEqual(report(self.packets)["adjudication"], mapping["adjudication"])

    def test_changed_run_results_rejected(self):
        self.prepare()
        self.complete_packets()
        write_jsonl(self.run / "results.jsonl", [])
        with self.assertRaisesRegex(ValueError, "Run artifacts changed"):
            report(self.packets)


if __name__ == "__main__":
    unittest.main()
