"""Async sliding-window rate limiter.

Alpaca's free tier limits to ~200 req/min. The default target of 150
req/min leaves headroom for small bursts. One limiter instance per
process -- if the service ever scales beyond replicas=1, this has to
move to Redis (noted in the Helm chart).
"""

from __future__ import annotations

import asyncio
import time
from collections import deque


class SlidingWindowRateLimiter:
    """Permit at most max_calls in any window_seconds-second window."""

    def __init__(self, max_calls: int = 150, window_seconds: float = 60.0) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_calls = max_calls
        self._window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    @property
    def max_calls(self) -> int:
        return self._max_calls

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._evict(now)
            if len(self._timestamps) >= self._max_calls:
                wait = self._timestamps[0] + self._window - now
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    self._evict(now)
            self._timestamps.append(now)

    def _evict(self, now: float) -> None:
        cutoff = now - self._window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
