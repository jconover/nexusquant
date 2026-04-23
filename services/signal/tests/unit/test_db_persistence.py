from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient


def test_successful_handler_inserts_one_row(client: TestClient, stub_db_pool: Any) -> None:
    resp = client.get("/signal/AAPL")
    assert resp.status_code == 200
    # BackgroundTasks run synchronously after the response in TestClient.
    assert len(stub_db_pool.executes) == 1

    sql, params = stub_db_pool.executes[0]
    assert sql.startswith("INSERT INTO signals")

    symbol, _ts, indicator_json, rule_result = params
    assert symbol == "AAPL"
    indicators = json.loads(indicator_json)
    assert set(indicators.keys()) == {
        "sma_20",
        "sma_50",
        "rsi_14",
        "vwap",
        "avg_volume_20",
        "last_close",
        "last_volume",
    }
    # Rule result is lowercased at the DB boundary to match the CHECK.
    assert rule_result == "hold"


def test_handler_still_returns_200_when_db_write_fails(
    client: TestClient, stub_db_pool: Any
) -> None:
    stub_db_pool.fail = True
    resp = client.get("/signal/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["signal"] in {"BUY", "SELL", "HOLD"}


def test_db_failure_increments_failure_counter(client: TestClient, stub_db_pool: Any) -> None:
    stub_db_pool.fail = True
    client.get("/signal/AAPL")
    body = client.get("/metrics").text
    assert "signal_db_write_failures_total" in body
    for line in body.splitlines():
        if line.startswith("signal_db_write_failures_total "):
            value = float(line.split()[1])
            assert value >= 1.0
            break
    else:
        raise AssertionError("signal_db_write_failures_total row not found")


def test_404_does_not_trigger_db_write(client: TestClient, stub_db_pool: Any) -> None:
    resp = client.get("/signal/TSLA")
    assert resp.status_code == 404
    assert stub_db_pool.executes == []
