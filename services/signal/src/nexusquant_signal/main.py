"""Signal service FastAPI app.

Lifespan builds the Alpaca client, rate limiter, bars cache, and logger
from AlpacaSettings at startup. The endpoint wires dependencies via
request.app.state so tests can override them.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from alpaca.data.historical import StockHistoricalDataClient
from fastapi import Depends, FastAPI, HTTPException, Request

from nexusquant_signal import alpaca_service
from nexusquant_signal.alpaca_clients import historical_data_client
from nexusquant_signal.alpaca_logger import get_alpaca_logger
from nexusquant_signal.cache import BarsCache, BarsCacheKey, ttl_for
from nexusquant_signal.config import AlpacaSettings, settings
from nexusquant_signal.indicators import (
    avg_volume,
    last_close,
    last_volume,
    rsi_wilder,
    sma,
    vwap,
)
from nexusquant_signal.rate_limiter import SlidingWindowRateLimiter
from nexusquant_signal.rules import evaluate
from nexusquant_signal.types import Bar
from nexusquant_signal.universe import is_in_universe


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # pydantic-settings reads required fields from env; mypy can't see that.
    alpaca_settings = AlpacaSettings()  # type: ignore[call-arg]
    app.state.alpaca_settings = alpaca_settings
    app.state.alpaca_client = historical_data_client(alpaca_settings)
    app.state.bars_cache = BarsCache()
    app.state.rate_limiter = SlidingWindowRateLimiter()
    app.state.alpaca_logger = get_alpaca_logger(settings.service_name)
    yield


app = FastAPI(title=settings.service_name, lifespan=lifespan)


# --- Dependency providers (tests override via app.dependency_overrides) ---


def get_cache(request: Request) -> BarsCache:
    return request.app.state.bars_cache  # type: ignore[no-any-return]


def get_alpaca_client(request: Request) -> StockHistoricalDataClient:
    return request.app.state.alpaca_client  # type: ignore[no-any-return]


def get_rate_limiter(request: Request) -> SlidingWindowRateLimiter:
    return request.app.state.rate_limiter  # type: ignore[no-any-return]


def get_alpaca_logger_dep(request: Request) -> logging.Logger:
    return request.app.state.alpaca_logger  # type: ignore[no-any-return]


# --- Endpoints ---


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ok"}


async def _cached_fetch(
    cache: BarsCache,
    symbol: str,
    timeframe: str,
    client: StockHistoricalDataClient,
    limiter: SlidingWindowRateLimiter,
    logger: logging.Logger,
) -> tuple[list[Bar], bool]:
    now = datetime.now(tz=UTC)
    if timeframe == "daily":
        key = BarsCacheKey(
            symbol=symbol,
            timeframe="daily",
            start_iso=(now - timedelta(days=200)).date().isoformat(),
            end_iso=now.date().isoformat(),
        )
    else:  # "minute"
        key = BarsCacheKey(
            symbol=symbol,
            timeframe="minute",
            start_iso=now.date().isoformat(),
            end_iso="session",
        )
    cached = cache.get(key)
    if cached is not None:
        return cached, True
    if timeframe == "daily":
        bars = await alpaca_service.fetch_daily_bars(client, symbol, limiter, logger)
    else:
        bars = await alpaca_service.fetch_intraday_bars(client, symbol, limiter, logger)
    cache.put(key, bars, ttl_for(timeframe))
    return bars, False


@app.get("/signal/{symbol}")
async def get_signal(
    symbol: str,
    cache: Annotated[BarsCache, Depends(get_cache)],
    client: Annotated[StockHistoricalDataClient, Depends(get_alpaca_client)],
    limiter: Annotated[SlidingWindowRateLimiter, Depends(get_rate_limiter)],
    alpaca_log: Annotated[logging.Logger, Depends(get_alpaca_logger_dep)],
) -> dict[str, Any]:
    if not is_in_universe(symbol):
        raise HTTPException(
            status_code=404,
            detail={"error": "symbol_not_in_phase_1_universe", "symbol": symbol},
        )

    try:
        daily_bars, daily_hit = await _cached_fetch(
            cache, symbol, "daily", client, limiter, alpaca_log
        )
        minute_bars, minute_hit = await _cached_fetch(
            cache, symbol, "minute", client, limiter, alpaca_log
        )
    except alpaca_service.AlpacaError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "alpaca_upstream_error", "message": str(e)},
        ) from e

    try:
        indicators_map = {
            "sma_20": sma(daily_bars, 20),
            "sma_50": sma(daily_bars, 50),
            "rsi_14": rsi_wilder(daily_bars, period=14),
            "vwap": vwap(minute_bars),
            "avg_volume_20": avg_volume(daily_bars, 20),
            "last_close": last_close(daily_bars),
            "last_volume": last_volume(daily_bars),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "insufficient_data", "message": str(e)},
        ) from e

    verdict = evaluate(
        last_close=indicators_map["last_close"],
        sma_20=indicators_map["sma_20"],
        sma_50=indicators_map["sma_50"],
        rsi_14=indicators_map["rsi_14"],
        last_volume=indicators_map["last_volume"],
        avg_volume_20=indicators_map["avg_volume_20"],
    )

    return {
        "symbol": symbol,
        "as_of": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "indicators": indicators_map,
        "signal": verdict.signal.value,
        "rules_passed": verdict.rules_passed,
        "data_source": "alpaca_rest",
        "cache_hit": daily_hit and minute_hit,
    }
