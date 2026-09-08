"""Shared serial pacing and bounded retries; never retries billing failures."""
import math
import random
import re
import time


def duration_seconds(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]+)?(?:ms|s|m|h|d))+", value):
        return None
    scales = {"ms": .001, "s": 1, "m": 60, "h": 3600, "d": 86400}
    return sum(float(n) * scales[u] for n, u in re.findall(r"([0-9]+(?:\.[0-9]+)?)(ms|s|m|h|d)", value))


class RateControl:
    def __init__(self, min_interval=0, target_tpm=0, retries=0, max_retry_wait=120,
                 clock=time.monotonic, sleep=time.sleep, jitter=None):
        self.min_interval, self.target_tpm = min_interval, target_tpm
        self.retries, self.max_retry_wait = retries, max_retry_wait
        self.clock, self.sleep = clock, sleep
        self.jitter = jitter or (lambda: random.uniform(.5, 1.5))
        self.next_allowed = 0

    def wait(self):
        started = self.clock()
        while self.next_allowed > self.clock():
            remaining = self.next_allowed - self.clock()
            print(f"  [Pacing] waiting {remaining:.1f}s before the next API call", flush=True)
            self.sleep(min(remaining, 30))
        self.next_allowed = self.clock() + self.min_interval
        return self.clock() - started

    def observe(self, usage):
        # Feedback pacing, not an exact token-bucket admission guarantee. Input
        # lengths can grow and other processes may share the account allowance.
        if self.target_tpm:
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            self.next_allowed = max(self.next_allowed, self.clock() + 60 * tokens / self.target_tpm)

    def retry_delay(self, details, retries_used, waited):
        if (retries_used >= self.retries or details.get("http_status") != 429
                or details.get("code") not in ("rate_limit_exceeded", "slow_down")
                or details.get("type") == "insufficient_quota"):
            return None
        if details.get("requested", 0) > details.get("limit", math.inf):
            return None
        limits = details.get("rate_limits", {})
        for resource in ("tokens", "project-tokens"):
            limit = limits.get(f"x-ratelimit-limit-{resource}")
            if limit is not None:
                if limit <= 0 or (details.get("type") == "tokens" and details.get("requested", 0) > limit):
                    return None
                if self.target_tpm:
                    self.target_tpm = min(self.target_tpm, .8 * limit)
        delays = []
        if "retry_after_seconds" in limits:
            delays.append(limits["retry_after_seconds"])
        for resource in ("tokens", "project-tokens", "requests"):
            remaining = limits.get(f"x-ratelimit-remaining-{resource}")
            implicated = (remaining is not None and remaining <= 0)
            implicated |= details.get("type") == "tokens" and resource in ("tokens", "project-tokens")
            implicated |= details.get("type") == "requests" and resource == "requests"
            if implicated:
                reset = duration_seconds(limits.get(f"x-ratelimit-reset-{resource}"))
                if reset is not None:
                    delays.append(reset)
        delay = max(delays) if delays else min(60, 10 * 2 ** min(retries_used, 4))
        delay = max(delay + self.jitter(), self.next_allowed - self.clock())
        if not math.isfinite(delay) or waited + delay > self.max_retry_wait:
            return None  # Never shorten a server delay just to fit our budget.
        return delay

    def defer(self, delay):
        self.next_allowed = max(self.next_allowed, self.clock() + delay)
