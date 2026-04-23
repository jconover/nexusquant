from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from nexusquant_signal.indicators import (
    avg_volume,
    last_close,
    last_volume,
    rsi_wilder,
    sma,
    vwap,
)
from nexusquant_signal.types import Bar

BASE_TS = datetime(2026, 4, 22, 13, 30, tzinfo=UTC)


def _bar(
    i: int,
    close: float,
    volume: float = 1000.0,
    high: float | None = None,
    low: float | None = None,
    open_: float | None = None,
) -> Bar:
    return Bar(
        symbol="TEST",
        ts=BASE_TS + timedelta(minutes=i),
        open=open_ if open_ is not None else close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=volume,
    )


# SMA -----------------------------------------------------------------


def test_sma_known_vector() -> None:
    bars = [_bar(i, float(i + 1)) for i in range(10)]  # closes 1..10
    assert sma(bars, 5) == pytest.approx(8.0)  # mean of 6..10
    assert sma(bars, 10) == pytest.approx(5.5)


def test_sma_uses_last_window_only() -> None:
    bars = [_bar(i, 1.0) for i in range(10)]
    bars += [_bar(i + 10, 100.0) for i in range(5)]
    assert sma(bars, 5) == pytest.approx(100.0)


def test_sma_insufficient_history_raises() -> None:
    bars = [_bar(i, 100.0) for i in range(5)]
    with pytest.raises(ValueError, match="SMA"):
        sma(bars, 10)


# RSI -----------------------------------------------------------------


def test_rsi_all_flat_returns_50() -> None:
    bars = [_bar(i, 100.0) for i in range(20)]
    assert rsi_wilder(bars, period=14) == pytest.approx(50.0)


def test_rsi_monotonic_up_returns_100() -> None:
    bars = [_bar(i, 100.0 + i) for i in range(20)]
    assert rsi_wilder(bars, period=14) == pytest.approx(100.0)


def test_rsi_monotonic_down_returns_0() -> None:
    bars = [_bar(i, 200.0 - i) for i in range(20)]
    assert rsi_wilder(bars, period=14) == pytest.approx(0.0)


def test_rsi_mixed_is_between_extremes() -> None:
    # Alternating +2 / -1 closes over 30 bars; gains outweigh losses so
    # RSI should settle well above 50 but below 100.
    closes = [100.0]
    for i in range(30):
        closes.append(closes[-1] + (2.0 if i % 2 == 0 else -1.0))
    bars = [_bar(i, c) for i, c in enumerate(closes)]
    rsi = rsi_wilder(bars, period=14)
    assert 50.0 < rsi < 100.0


def test_rsi_insufficient_history_raises() -> None:
    bars = [_bar(i, 100.0 + i) for i in range(14)]  # need period + 1 = 15
    with pytest.raises(ValueError, match="RSI"):
        rsi_wilder(bars, period=14)


# VWAP ----------------------------------------------------------------


def test_vwap_single_bar_equals_typical() -> None:
    bar = _bar(0, close=100.0, volume=1000.0, high=105.0, low=95.0)
    assert vwap([bar]) == pytest.approx(100.0)


def test_vwap_weighted_by_volume() -> None:
    b1 = _bar(0, close=100.0, volume=1000.0, high=100.0, low=100.0)
    b2 = _bar(1, close=200.0, volume=3000.0, high=200.0, low=200.0)
    # (100*1000 + 200*3000) / 4000 = 175
    assert vwap([b1, b2]) == pytest.approx(175.0)


def test_vwap_zero_volume_raises() -> None:
    bar = _bar(0, close=100.0, volume=0.0)
    with pytest.raises(ValueError, match="volume is zero"):
        vwap([bar])


def test_vwap_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        vwap([])


# avg_volume / last_* -------------------------------------------------


def test_avg_volume_known_vector() -> None:
    bars = [_bar(i, 100.0, volume=1000.0 * (i + 1)) for i in range(20)]
    # volumes 1000..20000; avg = 10500
    assert avg_volume(bars, 20) == pytest.approx(10500.0)


def test_avg_volume_insufficient_history_raises() -> None:
    bars = [_bar(i, 100.0) for i in range(5)]
    with pytest.raises(ValueError, match="avg_volume"):
        avg_volume(bars, 20)


def test_last_close_and_volume() -> None:
    bars = [_bar(i, 100.0 + i, volume=500.0 * (i + 1)) for i in range(5)]
    assert last_close(bars) == pytest.approx(104.0)
    assert last_volume(bars) == pytest.approx(2500.0)


def test_last_close_empty_raises() -> None:
    with pytest.raises(ValueError, match="last_close"):
        last_close([])


def test_last_volume_empty_raises() -> None:
    with pytest.raises(ValueError, match="last_volume"):
        last_volume([])
