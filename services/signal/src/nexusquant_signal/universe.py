"""Phase 1 symbol universe.

Hardcoded frozenset. Later phases replace this with the dynamic watchlist
loaded from candidates.parquet at market open. The 404 served for any
symbol outside this set is a reminder that symbol allowlisting is the
rule, not the exception.
"""

from __future__ import annotations

PHASE_1_SYMBOLS: frozenset[str] = frozenset({"AAPL", "MSFT", "NVDA", "SPY"})


def is_in_universe(symbol: str) -> bool:
    return symbol in PHASE_1_SYMBOLS
