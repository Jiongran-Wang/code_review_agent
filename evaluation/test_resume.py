"""Resume must preserve completed work and never reroll model-quality failures."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.run import main, read_jsonl, run_case, write_jsonl


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source"
        self.output = Path(self.temp.name) / "continued"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--limit", "2", "--output", str(self.source)]), 0)

    def resume(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(["--resume-from", str(self.source), "--output", str(self.output)])

    def test_only_zero_response_api_failure_is_retried(self):
        results = read_jsonl(self.source / "results.jsonl")
        failed = results[-1]
        failed.update(status="error", error="RateLimitError")
        failed["metrics"]["llm_responses"] = 0
        write_jsonl(self.source / "results.jsonl", results)
        original_bytes = (self.source / "results.jsonl").read_bytes()
        with patch("evaluation.run.run_case", wraps=run_case) as execute:
            self.assertEqual(self.resume(), 0)
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[0]["case_id"], failed["case_id"])
        self.assertEqual(execute.call_args.args[1], failed["system"])
        self.assertEqual((self.source / "results.jsonl").read_bytes(), original_bytes)
        new_results = read_jsonl(self.output / "results.jsonl")
        self.assertEqual(new_results[:3], results[:3])
        self.assertEqual(len(new_results), 4)
        self.assertTrue(all(r["status"] == "ok" for r in new_results))
        self.assertEqual(len(list((self.output / "resume_history").glob("*/results.jsonl"))), 1)

    def test_completed_run_makes_no_model_calls(self):
        with patch("evaluation.run.run_case") as execute:
            self.assertEqual(self.resume(), 0)
        execute.assert_not_called()

    def test_model_quality_failure_cannot_be_rerolled(self):
        results = read_jsonl(self.source / "results.jsonl")
        results[-1].update(status="error", error="invalid_final_review")
        write_jsonl(self.source / "results.jsonl", results)
        with self.assertRaises(SystemExit):
            self.resume()
        self.assertFalse(self.output.exists())

    def test_changed_prompt_refused_before_copy(self):
        manifest_path = self.source / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["prompt_hashes"]["agent"] = "changed"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(SystemExit):
            self.resume()
        self.assertFalse(self.output.exists())

    def test_partial_agent_api_failure_cannot_restart_silently(self):
        results = read_jsonl(self.source / "results.jsonl")
        results[-1].update(status="error", error="RateLimitError")
        results[-1]["metrics"]["llm_responses"] = 1
        write_jsonl(self.source / "results.jsonl", results)
        with self.assertRaises(SystemExit):
            self.resume()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
