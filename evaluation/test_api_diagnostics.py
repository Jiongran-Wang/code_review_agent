import unittest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from evaluation.api_diagnostics import error_hint, safe_api_error


class RateDiagnosticsTests(unittest.TestCase):
    def error(self, message, headers=None):
        return SimpleNamespace(
            body={"code": "rate_limit_exceeded", "type": "tokens", "message": message},
            status_code=429, response=SimpleNamespace(headers=headers or {}))

    def test_oversized_request_has_actionable_hint(self):
        details = safe_api_error(self.error(
            "org-private: Limit: 10000 / min. Requested: 12000. Use sk-secret"))
        self.assertEqual(details["requested"], 12000)
        self.assertEqual(details["limit"], 10000)
        self.assertIn("One request exceeds", error_hint(details))
        self.assertNotIn("private", str(details))
        self.assertNotIn("secret", str(details))

    def test_temporary_exhaustion_preserves_delay(self):
        details = safe_api_error(self.error("Limit: 30000, Used: 25000, Requested: 12000", {
            "x-ratelimit-limit-tokens": "30000",
            "x-ratelimit-remaining-tokens": "5000",
            "x-ratelimit-reset-tokens": "1m2.5s", "retry-after": "62.5"}))
        self.assertEqual(details["rate_limits"]["retry_after_seconds"], 62.5)
        self.assertNotIn("One request exceeds", error_hint(details))

    def test_untrusted_header_values_are_discarded(self):
        details = safe_api_error(self.error("Requested: 123sk-secret", {
            "authorization": "Bearer sk-secret", "retry-after": "sk-secret",
            "x-ratelimit-limit-tokens": "123sk-secret",
            "x-ratelimit-reset-tokens": "1s sk-secret"}))
        self.assertNotIn("rate_limits", details)
        self.assertNotIn("requested", details)
        self.assertNotIn("secret", str(details))

    def test_missing_headers_and_body_are_supported(self):
        self.assertEqual(safe_api_error(Exception("sk-secret")), {})

    def test_http_date_retry_after_preserves_server_delay(self):
        reset = datetime.now(timezone.utc) + timedelta(hours=1)
        details = safe_api_error(self.error("", {"retry-after": format_datetime(reset, usegmt=True)}))
        self.assertGreater(details["rate_limits"]["retry_after_seconds"], 3598)
        self.assertLessEqual(details["rate_limits"]["retry_after_seconds"], 3600)


if __name__ == "__main__":
    unittest.main()
