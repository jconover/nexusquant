"""Pure indicator functions over list[Bar].

No I/O. No pandas. Callers supply enough history and the correct
timeframe. ValueError on pre-condition violations; the endpoint layer
translates that to an HTTP error at the boundary.
"""

from __future__ import annotations

from itertools import pairwise

from nexusquant_signal.types import Bar


def sma(bars: list[Bar], window: int) -> float:
    if len(bars) < window:
        raise ValueError(f"need >= {window} bars for SMA({window}), got {len(bars)}")
    recent = bars[-window:]
    return sum(b.close for b in recent) / window


def avg_volume(bars: list[Bar], window: int) -> float:
    if len(bars) < window:
        raise ValueError(f"need >= {window} bars for avg_volume({window}), got {len(bars)}")
    recent = bars[-window:]
    return sum(b.volume for b in recent) / window


def last_close(bars: list[Bar]) -> float:
    if not bars:
        raise ValueError("last_close: empty bar list")
    return bars[-1].close


def last_volume(bars: list[Bar]) -> float:
    if not bars:
        raise ValueError("last_volume: empty bar list")
    return bars[-1].volume


def vwap(bars: list[Bar]) -> float:
    """Session VWAP from intraday bars.

    typical_price = (high + low + close) / 3
    vwap = sum(typical * volume) / sum(volume)
    """
    if not bars:
        raise ValueError("vwap: empty bar list")
    num = 0.0
    den = 0.0
    for b in bars:
        typical = (b.high + b.low + b.close) / 3.0
        num += typical * b.volume
        den += b.volume
    if den == 0.0:
        raise ValueError("vwap: total volume is zero")
    return num / den


def rsi_wilder(bars: list[Bar], period: int = 14) -> float:
    """Wilder's smoothed RSI.

    Needs >= period + 1 bars (one extra for the first delta). Flat
    inputs return 50.0. Purely monotonic inputs return 100.0 (up) or
    0.0 (down) once smoothing converges.
    """
    if len(bars) < period + 1:
        raise ValueError(f"need >= {period + 1} bars for RSI({period}), got {len(bars)}")

    gains: list[float] = []
    losses: list[float] = []
    for prev, curr in pairwise(bars):
        delta = curr.close - prev.close
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, loss in zip(gains[period:], losses[period:], strict=True):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)
