"""Pluggable client-side rate limiting.

Different model providers cap usage in different ways, and the right defense differs:

- **Concurrency caps** (DeepSeek: 500 pro / 2500 flash in-flight requests). Defended *reactively* —
  bound the worker pool and retry HTTP 429 with backoff. No proactive throttle is needed.
- **Rate caps** (OpenAI / Anthropic / most others: requests-per-minute AND tokens-per-minute).
  These must be defended *proactively* — you have to space requests and budget tokens before
  sending, because blowing the window gets you 429s (or billing surprises) no matter the
  concurrency.

This module is the seam for the second kind. The model client calls ``rate_limiter.acquire(...)``
before every request; the default is a no-op (DeepSeek path), and ``SlidingWindowRateLimiter``
enforces RPM/TPM when a provider needs it. Limits are account-level, so a single limiter instance
should be shared across all clients/threads hitting the same account.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Protocol, runtime_checkable


@runtime_checkable
class RateLimiter(Protocol):
    def acquire(self, *, tokens: int = 0) -> None:
        """Block until one request consuming ``tokens`` may proceed under the limit."""
        ...


class NoOpRateLimiter:
    """Default for concurrency-limited providers (e.g. DeepSeek): never throttles."""

    def acquire(self, *, tokens: int = 0) -> None:
        return None


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window limiter over a rolling window (default 60s).

    Enforces a max number of requests and/or a max number of tokens within the window. ``acquire``
    blocks until admitting one request of ``tokens`` would exceed neither ceiling, then records it.
    Pass ``tokens=0`` to enforce request-rate (RPM) only; set ``max_tokens`` to also enforce TPM.

    Account-level limits mean one instance should be shared across every client and thread that
    hits the same account.
    """

    def __init__(
        self,
        *,
        max_requests: int | None = None,
        max_tokens: int | None = None,
        window_seconds: float = 60.0,
    ) -> None:
        if max_requests is None and max_tokens is None:
            raise ValueError("set at least one of max_requests / max_tokens")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.window_seconds = window_seconds
        self._events: deque[tuple[float, int]] = deque()  # (timestamp, tokens)
        self._cv = threading.Condition()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._events and self._events[0][0] <= cutoff:
            self._events.popleft()

    def acquire(self, *, tokens: int = 0) -> None:
        with self._cv:
            while True:
                now = time.monotonic()
                self._prune(now)
                requests = len(self._events)
                used_tokens = sum(count for _, count in self._events)
                room_for_request = self.max_requests is None or requests + 1 <= self.max_requests
                room_for_tokens = self.max_tokens is None or used_tokens + tokens <= self.max_tokens
                if room_for_request and room_for_tokens:
                    self._events.append((now, tokens))
                    return
                if not self._events:
                    # A single request larger than the whole token budget would otherwise deadlock;
                    # admit it best-effort rather than hang forever.
                    self._events.append((now, tokens))
                    return
                # Capacity frees as the oldest event ages out of the window; wake then and re-check.
                wait = self.window_seconds - (now - self._events[0][0])
                self._cv.wait(timeout=max(wait, 0.01))
