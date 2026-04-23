from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest
from nexusquant_signal.cache import BarsCache, BarsCacheKey, ttl_for
from nexusquant_signal.types import Bar

# ---- BarsCache unit tests ---------------------------------------------


def _mkbar(i: int) -> Bar:
    return Bar(
        symbol="X",
        ts=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
        open=1.0,
        high=1.0,
        low=1.0,
        close=1.0,
        volume=1.0,
    )


def test_cache_miss_returns_none() -> None:
    c = BarsCache()
    assert c.get(BarsCacheKey("AAPL", "daily", "2026-01-01", "2026-04-01")) is None


def test_cache_hit_returns_stored_bars() -> None:
    c = BarsCache()
    key = BarsCacheKey("AAPL", "daily", "2026-01-01", "2026-04-01")
    bars = [_mkbar(0), _mkbar(1)]
    c.put(key, bars, ttl_seconds=60.0)
    assert c.get(key) == bars


def test_cache_entry_expires() -> None:
    c = BarsCache()
    key = BarsCacheKey("AAPL", "daily", "a", "b")
    c.put(key, [_mkbar(0)], ttl_seconds=0.01)
    time.sleep(0.05)
    assert c.get(key) is None
    assert len(c) == 0  # expired entry evicted on access


def test_cache_eviction_is_fifo_when_full() -> None:
    c = BarsCache(maxsize=2)
    k1 = BarsCacheKey("A", "daily", "s", "e")
    k2 = BarsCacheKey("B", "daily", "s", "e")
    k3 = BarsCacheKey("C", "daily", "s", "e")
    c.put(k1, [_mkbar(0)], 60.0)
    c.put(k2, [_mkbar(1)], 60.0)
    c.put(k3, [_mkbar(2)], 60.0)
    assert len(c) == 2
    assert c.get(k1) is None  # evicted
    assert c.get(k2) is not None
    assert c.get(k3) is not None


def test_ttl_for_unknown_timeframe_raises() -> None:
    with pytest.raises(ValueError, match="timeframe"):
        ttl_for("hourly")


def test_ttl_for_known_timeframes_positive() -> None:
    assert ttl_for("daily") > 0
    assert ttl_for("minute") > 0


# ---- Endpoint-level: second call hits cache, not Alpaca ----------------


def test_second_call_is_served_from_cache(client, stub_client) -> None:  # type: ignore[no-untyped-def]
    first = client.get("/signal/AAPL").json()
    assert first["cache_hit"] is False
    assert len(stub_client.calls) == 2  # daily + minute

    second = client.get("/signal/AAPL").json()
    assert second["cache_hit"] is True
    # No additional Alpaca calls.
    assert len(stub_client.calls) == 2
