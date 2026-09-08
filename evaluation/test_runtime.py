"""Behavioral tests of fixture isolation, agent execution and result recording."""
import copy
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from evaluation.fixture_router import FixtureRouter, blob_sha
from evaluation.run import run_case, parse_review, read_jsonl, main, RecordedClient
from evaluation.runtime import PROJECT, LLMClient, LLMResponse
from evaluation.api_diagnostics import safe_api_error, error_hint


def settings():
    return dict(backend="scripted", model="gpt-4o", max_output_tokens=256,
                max_iterations=8, temperature=None, timeout=1, token_budget=10000)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.row = read_jsonl(PROJECT / "evaluation/data/inputs.jsonl")[0]
        self.router = FixtureRouter(self.row)
        self.addCleanup(self.router.close)
        self.common = {"owner": self.router.owner, "repo": self.router.repo}

    def call(self, tool_name, **kwargs):
        args = kwargs if tool_name.startswith("memory_") else {**self.common, **kwargs}
        return self.router.execute(tool_name, args)

    def test_reads_and_unknown_tools_never_use_network(self):
        with patch("socket.socket", side_effect=AssertionError("Network used")):
            for name in ("get_pull_request", "get_pull_request_files", "get_pull_request_status"):
                self.assertNotIn("error", self.call(name, pull_number=1))
            self.assertNotIn("error", self.call("list_commits", sha="candidate"))
            self.assertEqual(self.call("get_pull_request_status", pull_number=1)["statuses"], [])
            self.assertIn("error", self.call("get_hidden_tests"))

    def test_base_head_and_missing_paths(self):
        self.assertEqual(self.call("get_file_contents", path="module.py")["content"],
                         self.row["base_files"]["module.py"])
        self.assertEqual(self.call("get_file_contents", path="module.py", branch="candidate")["content"],
                         self.row["head_files"]["module.py"])
        for path in ("../labels.jsonl", "/etc/passwd", "tests_hidden.py"):
            self.assertIn("error", self.call("get_file_contents", path=path, branch="candidate"))
        self.assertIn("error", self.call("get_file_contents", path="module.py", branch="missing"))

    def test_reject_cross_case_and_invalid_arguments(self):
        self.assertIn("error", self.router.execute("get_pull_request", {**self.common, "pull_number": 2}))
        self.assertIn("error", self.router.execute("get_pull_request", {**self.common, "repo": "other", "pull_number": 1}))
        self.assertIn("error", self.call("get_pull_request", pull_number="1"))
        self.assertIn("error", self.call("get_pull_request", pull_number=1, secret="unexpected"))

    def test_reject_labels_in_fixture(self):
        mixed = dict(self.row, issues=[{"description": "gold"}])
        with self.assertRaises(ValueError):
            FixtureRouter(mixed)

    def test_reference_sha_reads_and_stale_fix_write(self):
        head_sha = self.call("get_pull_request", pull_number=1)["head_sha"]
        original = self.call("get_file_contents", path="module.py", branch=head_sha)
        self.assertNotIn("error", self.call("create_branch", branch="fix", from_branch="candidate"))
        self.assertIn("error", self.call("create_or_update_file", path="module.py", branch="fix",
                                         message="fix", content="new", sha="stale"))
        self.assertNotIn("error", self.call("create_or_update_file", path="module.py", branch="fix",
                                            message="fix", content="new", sha=original["sha"]))
        self.assertEqual(self.call("get_file_contents", path="module.py", branch="fix")["content"], "new")
        self.assertEqual(self.call("get_file_contents", path="module.py", branch=head_sha), original)
        self.assertNotIn("error", self.call("create_pull_request", title="Fix", head="fix", base="candidate"))
        self.assertEqual(self.router.artifacts()["fix_prs"][0]["files"]["module.py"], "new")
        self.assertIn("error", self.call("create_or_update_file", path="module.py", branch="candidate",
                                         message="fix", content="new", sha=original["sha"]))

    def test_local_review_and_comment_capture(self):
        result = self.call("create_pull_request_review", pull_number=1, event="REQUEST_CHANGES",
                           body="Review", comments=[{"path": "module.py", "line": 999, "body": "Claim"}])
        self.assertEqual(result["state"], "REQUEST_CHANGES")
        self.assertEqual(self.router.reviews[0]["comments"][0]["line"], 999)
        self.assertNotIn("error", self.call("add_issue_comment", issue_number=1, body="Summary"))
        self.assertEqual(len(self.router.comments), 1)

    def test_six_memory_tools_are_isolated(self):
        from code_review_agent.tools import memory_tools as production
        original_path = production.MEMORY_FILE
        self.assertEqual(self.call("memory_get_all"), "")
        self.assertNotIn("error", self.call("memory_add_pattern", name="rule", description="description"))
        self.assertNotIn("error", self.call("memory_add_false_positive", pattern="example", reason="test"))
        self.assertNotIn("error", self.call("memory_update_developer_profile", author="alice",
                                            new_issues=[{"category": "logic", "severity": "high"}]))
        self.assertTrue(self.call("memory_get_developer_profile", author="alice")["found"])
        self.assertNotIn("error", self.call("memory_aggregate_patterns", repo=f"{self.router.owner}/{self.router.repo}",
                                            issues=[{"category": "logic", "severity": "high", "file": "module.py"}]))
        second = FixtureRouter(self.row)
        try:
            self.assertEqual(second.execute("memory_get_all", {}), "")
            self.assertFalse(second.execute("memory_get_developer_profile", {"author": "alice"})["found"])
        finally:
            second.close()
        self.assertEqual(production.MEMORY_FILE, original_path)

    def test_truncation_does_not_mutate_snapshot(self):
        self.router.MAX_FILE_CONTENT_CHARS = 5
        result = self.call("get_file_contents", path="module.py", branch="candidate")
        self.assertIn("truncated", result["content"])
        self.assertEqual(self.router.branches["candidate"], self.row["head_files"])

    def test_framework_does_not_expose_hidden_tests(self):
        result = self.call("detect_test_framework", branch="candidate")
        self.assertEqual(result["language"], "python")
        self.assertEqual(result["config_files_checked"], [])
        self.assertEqual(result["frameworks"], [])


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.row = read_jsonl(PROJECT / "evaluation/data/inputs.jsonl")[0]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "run"

    def test_actual_runner_smoke_and_clean_state(self):
        with patch("socket.socket", side_effect=AssertionError("Network used")):
            result = run_case(self.row, "agent", settings(), self.folder)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metrics"]["llm_attempts"], 3)
        self.assertEqual(result["metrics"]["submitted_reviews"], 1)
        self.assertEqual(result["metrics"]["tool_errors"], 0)
        raw = json.loads((self.folder / "raw.json").read_text())
        self.assertEqual(raw["memory"], [])
        requests = read_jsonl(self.folder / "requests.jsonl")
        serialized = json.dumps(requests)
        self.assertNotIn("reference_head_files", serialized)
        self.assertNotIn("gold_issue_id", serialized)
        self.assertEqual(len(requests[0]["request"]["tools"]), 17)

    def test_baseline_gets_all_fixture_context_and_no_tools(self):
        result = run_case(self.row, "baseline", settings(), self.folder)
        self.assertEqual(result["status"], "ok")
        requests = read_jsonl(self.folder / "requests.jsonl")
        self.assertEqual(len(requests), 1)
        self.assertIsNone(requests[0]["request"]["tools"])
        self.assertEqual(json.loads(requests[0]["request"]["messages"][0]["content"]), self.row)

    def test_incomplete_response_is_failure(self):
        class Truncated:
            def complete(self, **kwargs):
                return LLMResponse(content=[{"type": "text", "text": '{"decision":"APPROVE","findings":[]}'}],
                                   stop_reason="length", usage={"input_tokens": 3, "output_tokens": 2})
        result = run_case(self.row, "agent", settings(), self.folder, client_factory=lambda r: Truncated())
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["termination_reason"], "length")
        self.assertEqual(result["metrics"]["llm_attempts"], 1)

    def test_max_iteration_and_format_failures(self):
        options = dict(settings(), max_iterations=1)
        result = run_case(self.row, "agent", options, self.folder)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["termination_reason"], "max_iterations")
        class BadFormat:
            def complete(self, **kwargs):
                return LLMResponse(content=[{"type": "text", "text": "Looks good"}], stop_reason="end_turn", usage={})
        malformed = run_case(self.row, "baseline", settings(), self.folder / "malformed",
                             client_factory=lambda r: BadFormat())
        self.assertEqual(malformed["error"], "invalid_final_review")

    def test_failure_is_recorded_without_secret_exception_text(self):
        class Fails:
            def complete(self, **kwargs):
                raise RuntimeError("secret-key-value")
        result = run_case(self.row, "agent", settings(), self.folder, client_factory=lambda r: Fails())
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["metrics"]["input_tokens"])
        self.assertNotIn("secret-key-value", (self.folder / "requests.jsonl").read_text())

    def test_token_budget_stops_before_another_request(self):
        class UsesBudget:
            def complete(self, **kwargs):
                return LLMResponse(content=[], stop_reason="end_turn", usage={"input_tokens": 10, "output_tokens": 1})
        client = RecordedClient(UsesBudget(), Path(self.temp.name) / "log.jsonl", 10)
        client.complete([])
        with self.assertRaises(RuntimeError):
            client.complete([])
        self.assertEqual(client.attempts, 1)

    def test_parser_does_not_silently_accept_prose_or_conflicting_decision(self):
        for text in ('Looks good', '{"decision":"APPROVE"}',
                     '{"decision":"APPROVE","findings":[{"file":"x","line":1,"description":"bug"}]}'):
            with self.assertRaises(ValueError):
                parse_review(text)

    def test_live_preflight_needs_key_and_does_not_create_fake_results(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as exit_info:
                main(["--backend", "live", "--output", str(self.folder)])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertFalse(self.folder.exists())

    def test_prompted_key_is_not_saved_and_auth_failure_stops_batch(self):
        authentication_error = type("AuthenticationError", (Exception,), {})
        class RejectsKey:
            def complete(self, **kwargs):
                raise authentication_error("do-not-log-this-secret")
        captured = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), \
             patch("evaluation.run.getpass.getpass", return_value="  test-secret-value  "), \
             patch("evaluation.run.LLMClient", return_value=RejectsKey()) as client, \
             contextlib.redirect_stdout(captured):
            status = main(["--backend", "live", "--prompt-api-key", "--limit", "2", "--repeats", "2",
                           "--output", str(self.folder)])
        self.assertEqual(status, 1)
        client.assert_called_once()
        self.assertEqual(client.call_args.kwargs["api_key"], "test-secret-value")
        self.assertIn("AuthenticationError", captured.getvalue())
        self.assertEqual(len(read_jsonl(self.folder / "results.jsonl")), 1)
        summary = json.loads((self.folder / "execution_summary.json").read_text())
        self.assertFalse(summary["model_evaluated"])
        self.assertEqual(sum(group["not_run"] for group in summary["systems"].values()), 7)
        for path in self.folder.rglob("*"):
            if path.is_file():
                self.assertNotIn("test-secret-value", path.read_text())
                self.assertNotIn("do-not-log-this-secret", path.read_text())

    def test_quoted_prompt_key_rejected_without_run_artifacts(self):
        with patch("evaluation.run.getpass.getpass", return_value='"quoted-key"'), \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--backend", "live", "--prompt-api-key", "--output", str(self.folder)])
        self.assertFalse(self.folder.exists())

    def test_quota_error_is_reported_and_stops_after_one_call(self):
        rate_error = type("RateLimitError", (Exception,), {})
        class QuotaUnavailable:
            def complete(self, **kwargs):
                exc = rate_error("secret-must-not-be-logged")
                exc.status_code = 429
                exc.body = {"code": "credit_balance_exhausted", "type": "insufficient_quota"}
                raise exc
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), \
             patch("evaluation.run.LLMClient", return_value=QuotaUnavailable()) as client, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            status = main(["--backend", "live", "--limit", "2", "--output", str(self.folder)])
        client.assert_called_once()
        self.assertEqual(status, 1)
        self.assertIn("credit_balance_exhausted", output.getvalue())
        self.assertNotIn("secret-must-not-be-logged", output.getvalue())
        result = read_jsonl(self.folder / "results.jsonl")[0]
        self.assertEqual(result["api_error"]["http_status"], 429)
        summary = json.loads((self.folder / "execution_summary.json").read_text())
        self.assertEqual(summary["abort_reason"], "RateLimitError")
        self.assertEqual(sum(s["not_run"] for s in summary["systems"].values()), 3)

    def test_api_diagnostics_whitelist_excludes_arbitrary_secret_fields(self):
        exc = RuntimeError("secret-in-message")
        exc.body = {"error": {"code": "secret-in-code", "type": "secret-in-type"}}
        exc.status_code = 429
        self.assertEqual(safe_api_error(exc), {"http_status": 429})
        exc.body = {"error": {"code": "rate_limit_exceeded", "type": "rate_limit_error"}}
        self.assertEqual(safe_api_error(exc)["code"], "rate_limit_exceeded")
        self.assertIn("rate limit", error_hint(safe_api_error(exc)))


class APIClientTests(unittest.TestCase):
    def test_settings_and_finish_reason_preserved(self):
        with patch("code_review_agent.agent.llm_client.OpenAI") as sdk:
            client = LLMClient(api_key="test-placeholder", model="gpt-4o", temperature=0, seed=7,
                               max_tokens=123, max_retries=0, timeout=5)
            sdk.return_value.chat.completions.create.return_value = SimpleNamespace(
                model="gpt-4o-snapshot", id="test-response", system_fingerprint="test-fingerprint",
                usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3),
                choices=[SimpleNamespace(finish_reason="length", message=SimpleNamespace(content="partial", tool_calls=None))])
            response = client.complete([{"role": "user", "content": "Review"}])
            self.assertEqual(response.stop_reason, "length")
            self.assertEqual(response.model, "gpt-4o-snapshot")
            self.assertEqual(response.metadata["system_fingerprint"], "test-fingerprint")
            request = sdk.return_value.chat.completions.create.call_args.kwargs
            self.assertEqual((request["temperature"], request["seed"], request["max_tokens"]), (0, 7, 123))
            self.assertEqual(sdk.call_args.kwargs["max_retries"], 0)


if __name__ == "__main__":
    unittest.main()
