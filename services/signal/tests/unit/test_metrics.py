from __future__ import annotations

from fastapi.testclient import TestClient

EXPECTED_METRIC_NAMES = (
    "signals_computed_total",
    "signal_computation_latency_seconds",
    "alpaca_request_total",
    "alpaca_request_latency_seconds",
    "cache_hit_total",
    "cache_miss_total",
    "signal_db_write_failures_total",
    "rate_limit_hit_total",
)


def test_metrics_endpoint_returns_prometheus_text(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_metrics_endpoint_exposes_all_expected_counters(client: TestClient) -> None:
    # Drive the handler at least once so counters register non-zero where applicable.
    client.get("/signal/AAPL")
    body = client.get("/metrics").text
    for name in EXPECTED_METRIC_NAMES:
        assert name in body, f"missing metric: {name}"


def test_signals_computed_increments_on_success(client: TestClient) -> None:
    client.get("/signal/AAPL")
    body = client.get("/metrics").text
    # Flat inputs -> HOLD; counter row includes the signal label.
    assert 'signals_computed_total{signal="HOLD",symbol="AAPL"}' in body


def test_cache_miss_then_hit_increments_counters(client: TestClient) -> None:
    client.get("/signal/AAPL")  # misses on daily + minute
    client.get("/signal/AAPL")  # hits on both
    body = client.get("/metrics").text
    assert 'cache_miss_total{kind="daily"}' in body
    assert 'cache_miss_total{kind="minute"}' in body
    assert 'cache_hit_total{kind="daily"}' in body
    assert 'cache_hit_total{kind="minute"}' in body
