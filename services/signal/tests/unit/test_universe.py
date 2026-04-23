from __future__ import annotations

from nexusquant_signal.universe import PHASE_1_SYMBOLS, is_in_universe


def test_phase_1_symbols_has_expected_members() -> None:
    assert frozenset({"AAPL", "MSFT", "NVDA", "SPY"}) == PHASE_1_SYMBOLS


def test_phase_1_symbols_is_frozen() -> None:
    assert isinstance(PHASE_1_SYMBOLS, frozenset)


def test_is_in_universe_positive() -> None:
    for sym in ("AAPL", "MSFT", "NVDA", "SPY"):
        assert is_in_universe(sym), sym


def test_is_in_universe_negative() -> None:
    for sym in ("TSLA", "GOOG", "", "AAPL "):
        assert not is_in_universe(sym), sym


def test_is_in_universe_is_case_sensitive() -> None:
    assert not is_in_universe("aapl")
    assert not is_in_universe("Spy")
