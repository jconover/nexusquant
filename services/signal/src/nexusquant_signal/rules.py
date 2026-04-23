"""Phase 1 rule evaluator.

BUY  if last_close > sma_20 > sma_50 AND rsi_14 < 70 AND last_volume > avg_volume_20
SELL if last_close < sma_20 < sma_50 AND rsi_14 > 30
HOLD otherwise

rules_passed counts component conditions true for the chosen signal. Since
BUY/SELL are strict conjunctions, rules_passed is 3/2 when they trigger;
HOLD carries rules_passed=0 because HOLD has no affirmative conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Signal(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class Verdict:
    signal: Signal
    rules_passed: int


def evaluate(
    *,
    last_close: float,
    sma_20: float,
    sma_50: float,
    rsi_14: float,
    last_volume: float,
    avg_volume_20: float,
) -> Verdict:
    buy_conditions = (
        last_close > sma_20 and sma_20 > sma_50,
        rsi_14 < 70.0,
        last_volume > avg_volume_20,
    )
    if all(buy_conditions):
        return Verdict(Signal.BUY, sum(buy_conditions))

    sell_conditions = (
        last_close < sma_20 and sma_20 < sma_50,
        rsi_14 > 30.0,
    )
    if all(sell_conditions):
        return Verdict(Signal.SELL, sum(sell_conditions))

    return Verdict(Signal.HOLD, 0)
