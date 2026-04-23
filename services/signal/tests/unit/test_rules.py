from __future__ import annotations

from nexusquant_signal.rules import Signal, Verdict, evaluate


def _canonical_buy() -> dict[str, float]:
    """Inputs where all BUY conditions hold; adjust one per test to break them."""
    return {
        "last_close": 110.0,
        "sma_20": 105.0,
        "sma_50": 100.0,
        "rsi_14": 55.0,
        "last_volume": 2_000_000.0,
        "avg_volume_20": 1_000_000.0,
    }


def _canonical_sell() -> dict[str, float]:
    """Inputs where all SELL conditions hold."""
    return {
        "last_close": 90.0,
        "sma_20": 95.0,
        "sma_50": 100.0,
        "rsi_14": 55.0,
        "last_volume": 500_000.0,  # irrelevant for SELL
        "avg_volume_20": 1_000_000.0,
    }


# BUY path --------------------------------------------------------------


def test_buy_all_conditions_true() -> None:
    v = evaluate(**_canonical_buy())
    assert v == Verdict(Signal.BUY, 3)


def test_buy_breaks_when_close_not_above_sma20() -> None:
    inputs = _canonical_buy() | {"last_close": 105.0}  # equal, not greater
    assert evaluate(**inputs).signal != Signal.BUY


def test_buy_breaks_when_sma20_not_above_sma50() -> None:
    inputs = _canonical_buy() | {"sma_20": 100.0, "sma_50": 105.0}
    assert evaluate(**inputs).signal != Signal.BUY


def test_buy_breaks_at_rsi_70_exact() -> None:
    inputs = _canonical_buy() | {"rsi_14": 70.0}  # strict <
    v = evaluate(**inputs)
    assert v.signal != Signal.BUY


def test_buy_breaks_when_volume_not_above_average() -> None:
    inputs = _canonical_buy() | {"last_volume": 1_000_000.0}  # equal, not greater
    assert evaluate(**inputs).signal != Signal.BUY


# SELL path -------------------------------------------------------------


def test_sell_all_conditions_true() -> None:
    v = evaluate(**_canonical_sell())
    assert v == Verdict(Signal.SELL, 2)


def test_sell_breaks_when_close_not_below_sma20() -> None:
    inputs = _canonical_sell() | {"last_close": 95.0}  # equal
    assert evaluate(**inputs).signal != Signal.SELL


def test_sell_breaks_when_sma20_not_below_sma50() -> None:
    inputs = _canonical_sell() | {"sma_20": 100.0, "sma_50": 95.0}
    assert evaluate(**inputs).signal != Signal.SELL


def test_sell_breaks_at_rsi_30_exact() -> None:
    inputs = _canonical_sell() | {"rsi_14": 30.0}  # strict >
    assert evaluate(**inputs).signal != Signal.SELL


# HOLD path -------------------------------------------------------------


def test_hold_when_neither_path_qualifies() -> None:
    # mid-trend, neutral RSI: no trend edge
    inputs = {
        "last_close": 100.0,
        "sma_20": 100.0,
        "sma_50": 100.0,
        "rsi_14": 50.0,
        "last_volume": 1_000_000.0,
        "avg_volume_20": 1_000_000.0,
    }
    assert evaluate(**inputs) == Verdict(Signal.HOLD, 0)


def test_hold_on_rsi_extreme_oversold_for_sell() -> None:
    # downtrend but RSI <= 30 -> don't sell further
    inputs = _canonical_sell() | {"rsi_14": 25.0}
    assert evaluate(**inputs) == Verdict(Signal.HOLD, 0)


# Enum/dataclass hygiene -------------------------------------------------


def test_signal_enum_values_uppercase() -> None:
    assert Signal.BUY.value == "BUY"
    assert Signal.SELL.value == "SELL"
    assert Signal.HOLD.value == "HOLD"
