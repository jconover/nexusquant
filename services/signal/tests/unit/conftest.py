"""Shared Alpaca + DB pool stubs + client fixture for endpoint-level tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from fastapi.testclient import TestClient
from nexusquant_signal.cache import BarsCache
from nexusquant_signal.main import app, get_alpaca_client, get_db_pool


@dataclass
class FakeBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class FakeBarSet:
    def __init__(self, data: dict[str, list[FakeBar]]) -> None:
        self.data = data


class StubHistoricalClient:
    """Duck-typed replacement for StockHistoricalDataClient.

    Records every incoming request and returns deterministic flat-close
    bars by timeframe. Flat closes yield HOLD + rules_passed=0.
    """

    def __init__(self) -> None:
        self.calls: list[StockBarsRequest] = []

    def get_stock_bars(self, req: StockBarsRequest) -> FakeBarSet:
        self.calls.append(req)
        symbol = req.symbol_or_symbols if isinstance(req.symbol_or_symbols, str) else "AAPL"
        tf = str(req.timeframe)
        if tf == str(TimeFrame.Day):
            return FakeBarSet({symbol: _flat_daily(100)})
        if tf == str(TimeFrame.Minute):
            return FakeBarSet({symbol: _flat_minute(30)})
        raise AssertionError(f"unexpected timeframe: {tf}")


def _flat_daily(n: int) -> list[FakeBar]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        FakeBar(
            timestamp=base + timedelta(days=i),
            open=100.0,
            high=100.0,
            low=100.0,
            close=100.0,
            volume=1_000_000.0,
        )
        for i in range(n)
    ]


def _flat_minute(n: int) -> list[FakeBar]:
    base = datetime(2026, 4, 22, 13, 30, tzinfo=UTC)
    return [
        FakeBar(
            timestamp=base + timedelta(minutes=i),
            open=100.0,
            high=100.5,
            low=99.5,
            close=100.0,
            volume=10_000.0,
        )
        for i in range(n)
    ]


@dataclass
class StubDbPool:
    """Duck-typed replacement for AsyncConnectionPool.

    Records each execute(sql, params) call. Set fail=True to simulate a
    DB outage -- the persistence task must catch and log, response must
    still be 200.
    """

    executes: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)
    fail: bool = False

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[_StubConn]:
        yield _StubConn(self)


class _StubConn:
    def __init__(self, pool: StubDbPool) -> None:
        self.pool = pool

    async def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        if self.pool.fail:
            raise RuntimeError("stub DB failure")
        self.pool.executes.append((sql, params))


@pytest.fixture
def stub_client() -> StubHistoricalClient:
    return StubHistoricalClient()


@pytest.fixture
def stub_db_pool() -> StubDbPool:
    return StubDbPool()


@pytest.fixture
def client(stub_client: StubHistoricalClient, stub_db_pool: StubDbPool) -> Iterator[TestClient]:
    app.dependency_overrides[get_alpaca_client] = lambda: stub_client
    app.dependency_overrides[get_db_pool] = lambda: stub_db_pool
    with TestClient(app) as c:
        c.app.state.bars_cache = BarsCache()
        yield c
    app.dependency_overrides.clear()
