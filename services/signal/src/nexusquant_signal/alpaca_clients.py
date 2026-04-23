"""Alpaca SDK client factories.

Single place, single way. Phase 1 only constructs the historical-data
client; TradingClient lives in the executor service (Phase 2) and is
deliberately absent here. Promoting these factories to a shared library
is a Phase 2 task (see TODO.md) once the executor needs them.
"""

from __future__ import annotations

from alpaca.data.historical import StockHistoricalDataClient

from nexusquant_signal.config import AlpacaSettings


def historical_data_client(settings: AlpacaSettings) -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        api_key=settings.api_key_id,
        secret_key=settings.api_secret_key,
    )
