"""Small process-local TTL cache for Alpaca bar results.

cachetools.TTLCache doesn't support per-entry TTL, which this phase
needs: TTLs are shorter during market hours and longer when closed.
A custom class is lighter than maintaining four TTLCaches.

With replicas=1 this is fine. Any scale-out replaces it with Redis
(flagged in the Helm chart).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import NamedTuple

from nexusquant_signal.market_hours import is_market_hours
from nexusquant_signal.types import Bar


class BarsCacheKey(NamedTuple):
    symbol: str
    timeframe: str  # "daily" | "minute"
    start_iso: str
    end_iso: str


@dataclass(slots=True)
class _Entry:
    bars: list[Bar]
    expires_at_monotonic: float


DAILY_TTL_OPEN = 15 * 60.0
DAILY_TTL_CLOSED = 6 * 3600.0
MINUTE_TTL_OPEN = 60.0
MINUTE_TTL_CLOSED = 3600.0


def ttl_for(timeframe: str) -> float:
    if timeframe == "daily":
        return DAILY_TTL_OPEN if is_market_hours() else DAILY_TTL_CLOSED
    if timeframe == "minute":
        return MINUTE_TTL_OPEN if is_market_hours() else MINUTE_TTL_CLOSED
    raise ValueError(f"unknown timeframe: {timeframe}")


class BarsCache:
    def __init__(self, maxsize: int = 256) -> None:
        self._store: dict[BarsCacheKey, _Entry] = {}
        self._max = maxsize

    def get(self, key: BarsCacheKey) -> list[Bar] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() >= entry.expires_at_monotonic:
            del self._store[key]
            return None
        return entry.bars

    def put(self, key: BarsCacheKey, bars: list[Bar], ttl_seconds: float) -> None:
        if len(self._store) >= self._max and key not in self._store:
            self._store.pop(next(iter(self._store)))  # FIFO eviction
        self._store[key] = _Entry(bars, time.monotonic() + ttl_seconds)

    def __len__(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
