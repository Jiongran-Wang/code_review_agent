"""Safe API diagnostics: expose only allowlisted identifiers and rate-limit values."""
import argparse
import getpass
import os
import re
import sys
import warnings
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


ERROR_HINTS = {
    "invalid_api_key": "The API rejected the key. Enter an active full secret key.",
    "insufficient_quota": "API quota is unavailable. Check API credit balance and organization/project limits.",
    "credit_balance_exhausted": "The organization's prepaid API credits are exhausted. Check API billing.",
    "organization_spend_limit_exceeded": "The organization has reached its configured API spend limit.",
    "project_spend_limit_exceeded": "The project has reached its configured API spend limit.",
    "organization_usage_limit_exceeded": "The organization has reached its assigned API usage limit.",
    "rate_limit_exceeded": "The request/token rate limit was reached. Check model-specific limits. Waiting helps only if a single request fits the limit; otherwise reduce the request size or use a model/project with sufficient capacity.",
    "slow_down": "The service requested slower traffic. Wait before retrying.",
    "model_not_found": "This model is unavailable to the selected API project or the model ID is incorrect.",
    "server_is_overloaded": "The model is temporarily overloaded. Retry after the service delay.",
}


def safe_api_error(exc):
    body = getattr(exc, "body", None)
    body = body if isinstance(body, dict) else {}
    if isinstance(body.get("error"), dict):
        body = body["error"]
    code = getattr(exc, "code", None) or body.get("code")
    error_type = getattr(exc, "type", None) or body.get("type")
    # A strict allowlist prevents a custom endpoint echoing a secret in a field
    # that is normally a short diagnostic identifier.
    details = {}
    if isinstance(code, str) and code in ERROR_HINTS:
        details["code"] = code
    if error_type in ("insufficient_quota", "rate_limit_error", "invalid_request_error", "tokens", "requests"):
        details["type"] = error_type
    status = getattr(exc, "status_code", None)
    if type(status) is int and 400 <= status <= 599:
        details["http_status"] = status
    # Never retain whole headers or message text (which can contain credentials).
    headers = getattr(getattr(exc, "response", None), "headers", {})
    rate_limits = {}
    for resource in ("requests", "tokens", "project-tokens"):
        for field in ("limit", "remaining", "reset"):
            name = f"x-ratelimit-{field}-{resource}"
            value = headers.get(name) if hasattr(headers, "get") else None
            pattern = r"(?:[0-9]{1,9}(?:\.[0-9]{1,3})?(?:ms|s|m|h|d)){1,5}" if field == "reset" else r"[0-9]{1,15}"
            if isinstance(value, str) and re.fullmatch(pattern, value):
                rate_limits[name] = value if field == "reset" else int(value)
    retry = headers.get("retry-after") if hasattr(headers, "get") else None
    if isinstance(retry, str) and re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,3})?", retry):
        rate_limits["retry_after_seconds"] = float(retry)
    elif isinstance(retry, str) and len(retry) <= 128:
        try:
            reset = parsedate_to_datetime(retry)
            if reset.tzinfo is not None:
                rate_limits["retry_after_seconds"] = max(0., (reset - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    if rate_limits:
        details["rate_limits"] = rate_limits
    # OpenAI commonly includes these measurements in a rate-limit error message.
    # Extract numbers only; never copy surrounding text or organization IDs.
    message = body.get("message")
    if code == "rate_limit_exceeded" and isinstance(message, str):
        for field in ("limit", "used", "requested"):
            match = re.search(r"\b" + field + r":\s*([0-9]{1,15})(?:\.0+)?(?=[\s,.;]|$)", message, re.IGNORECASE)
            if match:
                details[field] = int(match.group(1))
    return details


def error_hint(details):
    if (details.get("code") == "rate_limit_exceeded"
            and "requested" in details and "limit" in details
            and details["requested"] > details["limit"]):
        return ("One request exceeds the rate limit. Waiting or reducing the number of cases will not fix it. "
                "Reduce the request size or use a model/project with sufficient capacity.")
    return ERROR_HINTS.get(details.get("code"), ERROR_HINTS["insufficient_quota"]
                          if details.get("type") == "insufficient_quota"
                          else "Check API billing, model access and rate limits; the precise cause is not available.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-4o")
    args = parser.parse_args()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("OpenAI API key (hidden): ").strip()
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        parser.error("Run this command in a terminal that supports hidden input")
    if not key or any(c.isspace() for c in key) or key[0] in "\"'" or key[-1] in "\"'":
        parser.error("Paste the full key without quotes or embedded whitespace")
    from openai import OpenAI
    try:
        with OpenAI(api_key=key, base_url=os.getenv("OPENAI_BASE_URL"), timeout=30, max_retries=0) as client:
            client.chat.completions.create(model=args.model,
                messages=[{"role": "user", "content": "Say OK."}], max_tokens=1)
    except Exception as exc:
        details = safe_api_error(exc)
        print("API check failed:", type(exc).__name__, details)
        print(error_hint(details))
        return 1
    print("API check passed: the project can make a small GPT-4o-style Chat Completions request.")
    print("This does not establish that the larger benchmark requests fit your token-rate limits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
