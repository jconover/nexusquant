from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
SIGNAL_SCHEMA = json.loads((REPO_ROOT / "schemas" / "get_signal.json").read_text())["response"]


def test_signal_endpoint_returns_200_and_valid_schema(client: TestClient) -> None:
    resp = client.get("/signal/AAPL")
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    Draft202012Validator(SIGNAL_SCHEMA).validate(body)


def test_signal_endpoint_reports_hold_on_flat_inputs(client: TestClient) -> None:
    body = client.get("/signal/AAPL").json()
    assert body["signal"] == "HOLD"
    assert body["rules_passed"] == 0


def test_signal_endpoint_data_source_and_cache_hit_flags(client, stub_client) -> None:  # type: ignore[no-untyped-def]
    body = client.get("/signal/AAPL").json()
    assert body["data_source"] == "alpaca_rest"
    assert body["cache_hit"] is False
    # One call per timeframe (daily + minute)
    assert len(stub_client.calls) == 2


def test_signal_endpoint_indicator_keys(client: TestClient) -> None:
    body = client.get("/signal/AAPL").json()
    assert set(body["indicators"].keys()) == {
        "sma_20",
        "sma_50",
        "rsi_14",
        "vwap",
        "avg_volume_20",
        "last_close",
        "last_volume",
    }
