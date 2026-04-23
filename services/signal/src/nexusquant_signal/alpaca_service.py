"""Alpaca historical-data boundary.

Everything that touches alpaca-py lives here:
- HTTP calls go through the rate limiter before leaving the process.
- Structured log lines bracket every call (request + response or error).
- BarSet -> list[Bar] conversion happens here, so pandas/numpy types
  never leak to the indicator or endpoint layer.

alpaca-py's historical client is synchronous (requests-based); we run
it in a worker thread via asyncio.to_thread to keep the event loop
responsive.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from nexusquant_signal import metrics
from nexusquant_signal.alpaca_logger import AlpacaLogEvent, log_alpaca_event
from nexusquant_signal.market_hours import ET
from nexusquant_signal.rate_limiter import SlidingWindowRateLimiter
from nexusquant_signal.types import Bar

if TYPE_CHECKING:
    pass


class AlpacaError(Exception):
    """Wraps any alpaca-py failure the service bubbles to the caller."""


_ENDPOINT = "/v2/stocks/bars"
_METHOD = "GET"
_SERVICE = "signal"


def _bar_from_alpaca(symbol: str, raw: object) -> Bar:
    return Bar(
        symbol=symbol,
        ts=raw.timestamp,  # type: ignore[attr-defined]
        open=float(raw.open),  # type: ignore[attr-defined]
        high=float(raw.high),  # type: ignore[attr-defined]
        low=float(raw.low),  # type: ignore[attr-defined]
        close=float(raw.close),  # type: ignore[attr-defined]
        volume=float(raw.volume),  # type: ignore[attr-defined]
    )


def _extract(bar_set: object, symbol: str) -> list[Bar]:
    data = getattr(bar_set, "data", None) or {}
    raw = data.get(symbol, [])
    return [_bar_from_alpaca(symbol, r) for r in raw]


async def _call_with_instrumentation(
    client: StockHistoricalDataClient,
    req: StockBarsRequest,
    symbol: str,
    limiter: SlidingWindowRateLimiter,
    logger: logging.Logger,
) -> object:
    await limiter.acquire()
    log_alpaca_event(
        logger,
        AlpacaLogEvent(
            service=_SERVICE,
            direction="req",
            endpoint=_ENDPOINT,
            method=_METHOD,
            symbol=symbol,
        ),
    )
    t0 = time.monotonic()
    try:
        bar_set = await asyncio.to_thread(client.get_stock_bars, req)
    except Exception as e:
        elapsed = time.monotonic() - t0
        status = getattr(e, "status_code", None)
        if status == 429:
            metrics.rate_limit_hit_total.inc()
        metrics.alpaca_request_total.labels(
            endpoint=_ENDPOINT,
            status_code=str(status) if status is not None else "error",
        ).inc()
        metrics.alpaca_request_latency_seconds.labels(endpoint=_ENDPOINT).observe(elapsed)
        log_alpaca_event(
            logger,
            AlpacaLogEvent(
                service=_SERVICE,
                direction="res",
                endpoint=_ENDPOINT,
                method=_METHOD,
                symbol=symbol,
                latency_ms=elapsed * 1000,
                error_code=type(e).__name__,
            ),
        )
        raise AlpacaError(str(e)) from e
    elapsed = time.monotonic() - t0
    metrics.alpaca_request_total.labels(endpoint=_ENDPOINT, status_code="200").inc()
    metrics.alpaca_request_latency_seconds.labels(endpoint=_ENDPOINT).observe(elapsed)
    log_alpaca_event(
        logger,
        AlpacaLogEvent(
            service=_SERVICE,
            direction="res",
            endpoint=_ENDPOINT,
            method=_METHOD,
            symbol=symbol,
            status_code=200,
            latency_ms=elapsed * 1000,
        ),
    )
    return bar_set


async def fetch_daily_bars(
    client: StockHistoricalDataClient,
    symbol: str,
    limiter: SlidingWindowRateLimiter,
    logger: logging.Logger,
    lookback_days: int = 100,
) -> list[Bar]:
    """Last ~100 trading days of daily bars. Extra calendar-day buffer
    for weekends and holidays; the indicator layer trims to what it needs."""
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=lookback_days * 2)
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,  # free-tier plan; SIP requires paid subscription
    )
    bar_set = await _call_with_instrumentation(client, req, symbol, limiter, logger)
    return _extract(bar_set, symbol)


async def fetch_intraday_bars(
    client: StockHistoricalDataClient,
    symbol: str,
    limiter: SlidingWindowRateLimiter,
    logger: logging.Logger,
) -> list[Bar]:
    """Today's minute bars from the regular-session open, used for VWAP."""
    now_et = datetime.now(tz=ET)
    session_open_et = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    start = session_open_et.astimezone(UTC)
    end = datetime.now(tz=UTC)
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end,
        feed=DataFeed.IEX,  # free-tier plan; SIP requires paid subscription
    )
    bar_set = await _call_with_instrumentation(client, req, symbol, limiter, logger)
    return _extract(bar_set, symbol)
