"""Live-Alpaca integration test.

Skipped unless RUN_ALPACA_INTEGRATION=1 is set. Reads paper keys from
the real environment (typically loaded from repo-root .env). Never
hits a live trading endpoint; alpaca-paper/SKILL.md's must_be_paper
validators still gate AlpacaSettings construction.
"""

from __future__ import annotations

import math
import os

import pytest
from nexusquant_signal.alpaca_clients import historical_data_client
from nexusquant_signal.alpaca_logger import get_alpaca_logger
from nexusquant_signal.alpaca_service import fetch_daily_bars, fetch_intraday_bars
from nexusquant_signal.config import AlpacaSettings
from nexusquant_signal.indicators import (
    avg_volume,
    last_close,
    last_volume,
    rsi_wilder,
    sma,
)
from nexusquant_signal.rate_limiter import SlidingWindowRateLimiter
from nexusquant_signal.rules import Signal, evaluate

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_ALPACA_INTEGRATION"),
    reason="integration tests gated by RUN_ALPACA_INTEGRATION=1",
)


@pytest.mark.asyncio
async def test_aapl_daily_plus_minute_roundtrip() -> None:
    settings = AlpacaSettings()  # type: ignore[call-arg]
    client = historical_data_client(settings)
    limiter = SlidingWindowRateLimiter()
    logger = get_alpaca_logger("signal-integration")

    # 100 trading days of daily bars -- required by SMA(50).
    daily = await fetch_daily_bars(client, "AAPL", limiter, logger, lookback_days=100)
    assert len(daily) >= 50, f"need >=50 daily bars, got {len(daily)}"
    for b in daily:
        assert b.close > 0 and math.isfinite(b.close), f"bad close: {b.close}"
        assert b.volume >= 0 and math.isfinite(b.volume), f"bad volume: {b.volume}"

    # Today's minute bars. Outside RTH the bar count may be small or zero;
    # we only exercise VWAP when we have bars, so we don't make assertions
    # that fail over a weekend.
    minute = await fetch_intraday_bars(client, "AAPL", limiter, logger)

    sma_20 = sma(daily, 20)
    sma_50 = sma(daily, 50)
    rsi = rsi_wilder(daily, period=14)
    avg_vol_20 = avg_volume(daily, 20)
    lc = last_close(daily)
    lv = last_volume(daily)

    for name, value in (
        ("sma_20", sma_20),
        ("sma_50", sma_50),
        ("rsi_14", rsi),
        ("avg_volume_20", avg_vol_20),
        ("last_close", lc),
        ("last_volume", lv),
    ):
        assert math.isfinite(value), f"{name} not finite: {value}"
    assert 0.0 <= rsi <= 100.0
    assert sma_20 > 0 and sma_50 > 0 and lc > 0 and avg_vol_20 > 0

    verdict = evaluate(
        last_close=lc,
        sma_20=sma_20,
        sma_50=sma_50,
        rsi_14=rsi,
        last_volume=lv,
        avg_volume_20=avg_vol_20,
    )
    assert verdict.signal in {Signal.BUY, Signal.SELL, Signal.HOLD}
    assert verdict.rules_passed >= 0

    # Minute-bar sanity only when bars came back.
    if minute:
        for b in minute:
            assert b.high >= b.low
            assert b.volume >= 0
