"""Typed primitives for the signal service.

Bar is the canonical intraday or daily OHLCV record. Alpaca responses
are converted to list[Bar] at the SDK boundary so pandas types do not
leak into the indicator or endpoint layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
