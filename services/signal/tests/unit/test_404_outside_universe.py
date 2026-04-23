from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("symbol", ["TSLA", "GOOG", "QQQ", "AMZN"])
def test_outside_universe_returns_404(
    client: TestClient,
    stub_client,
    symbol: str,  # type: ignore[no-untyped-def]
) -> None:
    resp = client.get(f"/signal/{symbol}")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error"] == "symbol_not_in_phase_1_universe"
    assert body["detail"]["symbol"] == symbol
    # Alpaca must not be called for a 404.
    assert len(stub_client.calls) == 0


@pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "NVDA", "SPY"])
def test_inside_universe_does_not_404(client: TestClient, symbol: str) -> None:
    resp = client.get(f"/signal/{symbol}")
    assert resp.status_code == 200, resp.text
