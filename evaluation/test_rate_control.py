"""Test real retry/pacing behavior with a fake clock and no API calls."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from evaluation.rate_control import RateControl, duration_seconds
from evaluation.run import RecordedClient, read_jsonl, run_case
from evaluation.runtime import LLMResponse, PROJECT


class FakeClock:
    def __init__(self):
        self.now, self.sleeps = 0., []

    def clock(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


class RateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = FakeClock()

    def control(self, **kwargs):
        return RateControl(clock=self.clock.clock, sleep=self.clock.sleep,
                           jitter=lambda: 1., **kwargs)

    def error(self, code="rate_limit_exceeded", headers=None):
        exc = RuntimeError("secret-must-not-be-logged")
        exc.status_code = 429
        exc.body = {"code": code, "type": "tokens"}
        exc.response = SimpleNamespace(headers=headers or {})
        return exc

    def test_shared_pacing_spans_two_clients(self):
        control = self.control(min_interval=30, target_tpm=48000)
        response = LLMResponse([], "end_turn", {"input_tokens": 32000, "output_tokens": 0})
        inner = SimpleNamespace(complete=lambda **kw: response)
        clients = [RecordedClient(inner, Path(self.temp.name) / f"{n}.jsonl", 100000, control) for n in range(2)]
        with contextlib.redirect_stdout(io.StringIO()):
            for client in clients:
                client.complete([])
        self.assertEqual(self.clock.now, 40.)
        self.assertEqual(clients[1].pacing_wait_ms, 40000)
        self.assertTrue(all(s <= 30 for s in self.clock.sleeps))

    def test_real_header_sample_uses_token_reset_not_unexhausted_request_reset(self):
        control = self.control(retries=3)
        details = {"code": "rate_limit_exceeded", "type": "tokens", "http_status": 429,
                   "rate_limits": {"retry_after_seconds": 10.,
                                   "x-ratelimit-remaining-requests": 46,
                                   "x-ratelimit-reset-requests": "1h27m4.995s",
                                   "x-ratelimit-reset-tokens": "54.562s"}}
        self.assertAlmostEqual(control.retry_delay(details, 0, 0), 55.562)

    def test_retries_current_call_preserves_request_and_logs_attempts(self):
        requests = []
        def complete(**kwargs):
            requests.append(kwargs)
            if len(requests) == 1:
                raise self.error(headers={"retry-after": "10"})
            return LLMResponse([], "end_turn", {"input_tokens": 20, "output_tokens": 2})
        client = RecordedClient(SimpleNamespace(complete=complete), Path(self.temp.name)/"log.jsonl",
                                100000, self.control(retries=2))
        with contextlib.redirect_stdout(io.StringIO()):
            client.complete([{"role": "user", "content": "review"}], system="rubric", tools=[])
        self.assertEqual(requests[0], requests[1])
        self.assertEqual((client.attempts, client.rate_limit_retries), (2, 1))
        self.assertEqual((client.input_tokens, client.output_tokens), (20, 2))
        self.assertEqual(self.clock.now, 11.)
        self.assertEqual(len(client.records), 3)
        self.assertNotIn("secret-must", client.path.read_text())

    def test_billing_is_never_retried(self):
        for code in ("credit_balance_exhausted", "insufficient_quota", "project_spend_limit_exceeded"):
            self.assertIsNone(self.control(retries=3).retry_delay(
                {"code": code, "http_status": 429}, 0, 0))

    def test_oversized_request_is_not_retried(self):
        self.assertIsNone(self.control(retries=3).retry_delay(
            {"code": "rate_limit_exceeded", "http_status": 429, "limit": 10000, "requested": 17000}, 0, 0))

    def test_long_reset_is_not_shortened(self):
        details = {"code": "rate_limit_exceeded", "http_status": 429, "type": "requests",
                   "rate_limits": {"x-ratelimit-remaining-requests": 0,
                                   "x-ratelimit-reset-requests": "1h", "retry_after_seconds": 10}}
        self.assertIsNone(self.control(retries=3, max_retry_wait=180).retry_delay(details, 0, 0))

    def test_cumulative_wait_and_attempt_bounds(self):
        details = {"code": "rate_limit_exceeded", "http_status": 429,
                   "rate_limits": {"retry_after_seconds": 60}}
        control = self.control(retries=2, max_retry_wait=120)
        self.assertEqual(control.retry_delay(details, 0, 0), 61)
        self.assertIsNone(control.retry_delay(details, 1, 61))
        self.assertIsNone(control.retry_delay(details, 2, 0))

    def test_repeated_failure_stops_with_original_exception(self):
        exc = self.error()
        def fail(**kwargs):
            raise exc
        client = RecordedClient(SimpleNamespace(complete=fail), Path(self.temp.name)/"failure.jsonl",
                                100000, self.control(retries=2, max_retry_wait=180))
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError) as caught:
            client.complete([])
        self.assertIs(caught.exception, exc)
        self.assertEqual((client.attempts, client.rate_limit_retries), (3, 2))

    def test_server_limit_reduces_feedback_target(self):
        control = self.control(retries=2, target_tpm=48000)
        control.retry_delay({"code": "rate_limit_exceeded", "http_status": 429,
                             "rate_limits": {"x-ratelimit-limit-tokens": 30000}}, 0, 0)
        self.assertEqual(control.target_tpm, 24000)

    def test_duration_parsing(self):
        self.assertAlmostEqual(duration_seconds("1h27m4.995s"), 5224.995)
        self.assertEqual(duration_seconds("250ms"), .25)
        self.assertIsNone(duration_seconds("secret"))

    def test_agent_retry_does_not_replay_completed_tool(self):
        seen = []
        def complete(**kwargs):
            seen.append(kwargs)
            if len(seen) == 1:
                return LLMResponse([{"type": "tool_use", "id": "tool-1", "name": "get_pull_request",
                                     "input": {"owner": "benchmark", "repo": row["case_id"], "pull_number": 1}}],
                                   "tool_use", {"input_tokens": 10, "output_tokens": 5})
            if len(seen) == 2:
                raise self.error(headers={"retry-after": "1"})
            return LLMResponse([{"type": "text", "text": '{"decision":"APPROVE","findings":[]}'}],
                               "end_turn", {"input_tokens": 10, "output_tokens": 5})
        row = read_jsonl(PROJECT / "evaluation/data/inputs.jsonl")[0]
        settings = dict(backend="scripted", model="gpt-4o-mini", max_output_tokens=2048,
                        max_iterations=8, temperature=0, timeout=60, token_budget=100000)
        folder = Path(self.temp.name)/"agent"
        with contextlib.redirect_stdout(io.StringIO()):
            result = run_case(row, "agent", settings, folder,
                              client_factory=lambda router: SimpleNamespace(complete=complete),
                              rate_control=self.control(retries=2))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["metrics"]["tool_calls"], 1)
        self.assertEqual(result["metrics"]["llm_attempts"], 3)
        self.assertEqual(result["metrics"]["rate_limit_retries"], 1)


if __name__ == "__main__":
    unittest.main()
