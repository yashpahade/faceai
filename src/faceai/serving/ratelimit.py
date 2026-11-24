"""
Rate limiting (Phase E): ek IP kitni requests kar sakta hai.

Admission control (Phase 4) poori service ko overload se bachata hai. Rate limit ek CLIENT ko
abuse se rokta hai:
- /v1/auth/login: password brute force (1000 guesses/minute -> 10)
- /v1/auth/face-login, /v1/liveness/*: chehre ke saath brute force / enumeration
- signup spam

Token bucket: har IP ke paas `capacity` tokens; har request 1 token; tokens `rate`/second se
wapas bharte hain. Burst allowed (capacity), lambi abuse nahi (rate).

In-memory = sirf ek process. Kai replicas pe Redis-backed limiter chahiye (ya reverse proxy /
API gateway pe limit). Client IP: proxy ke peeche `X-Forwarded-For` sirf TRUSTED proxy se maano.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class Rule:
    prefix: str
    capacity: float  # burst
    per_minute: float  # sustained


DEFAULT_RULES = [
    Rule("/v1/auth/login", 10, 10),
    Rule("/v1/auth/signup", 5, 5),
    Rule("/v1/auth/face-login", 10, 10),
    Rule("/v1/auth/reset-password", 5, 5),  # account takeover attempts
    Rule("/v1/liveness/", 20, 20),
]


class RateLimiter:
    def __init__(self, rules: list[Rule], clock=time.monotonic, max_keys: int = 100_000):
        self.rules = rules
        self.clock = clock
        self.max_keys = max_keys
        self._buckets: dict[tuple[str, str], tuple[float, float]] = {}  # (rule, ip) -> (tokens, t)
        self._lock = threading.Lock()

    def rule_for(self, path: str) -> Rule | None:
        return next((r for r in self.rules if path.startswith(r.prefix)), None)

    def check(self, path: str, client: str) -> float | None:
        """None = allowed. Warna: kitne seconds baad retry kare (Retry-After)."""
        rule = self.rule_for(path)
        if rule is None:
            return None
        now = self.clock()
        rate = rule.per_minute / 60.0
        key = (rule.prefix, client)
        with self._lock:
            if len(self._buckets) > self.max_keys:  # memory bound (bahut saare IPs ka attack)
                self._buckets.clear()
            tokens, last = self._buckets.get(key, (rule.capacity, now))
            tokens = min(rule.capacity, tokens + (now - last) * rate)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return max(1.0, (1 - tokens) / rate)
            self._buckets[key] = (tokens - 1, now)
            return None


def client_ip(headers, peer: str | None, trusted_proxies: set[str]) -> str:
    """Proxy ke peeche asli client IP. X-Forwarded-For sirf trusted proxy se (warna spoof)."""
    peer = peer or "unknown"
    if peer in trusted_proxies:
        xff = headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return peer
