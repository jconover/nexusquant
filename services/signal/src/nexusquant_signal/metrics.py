"""Prometheus metrics for the signal service.

Counter and histogram definitions live here so every wirer imports a
single source of truth. The /metrics endpoint is mounted in main.py.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

signals_computed_total = Counter(
    "signals_computed_total",
    "Count of successfully computed signals, labelled by symbol and verdict.",
    ["symbol", "signal"],
)

signal_computation_latency_seconds = Histogram(
    "signal_computation_latency_seconds",
    "End-to-end latency of the /signal/{symbol} handler.",
)

alpaca_request_total = Counter(
    "alpaca_request_total",
    "Outbound Alpaca API requests, labelled by endpoint and response status.",
    ["endpoint", "status_code"],
)

alpaca_request_latency_seconds = Histogram(
    "alpaca_request_latency_seconds",
    "Wall-clock latency of Alpaca API calls, labelled by endpoint.",
    ["endpoint"],
)

cache_hit_total = Counter(
    "cache_hit_total",
    "BarsCache hits, labelled by timeframe kind (daily | minute).",
    ["kind"],
)

cache_miss_total = Counter(
    "cache_miss_total",
    "BarsCache misses, labelled by timeframe kind (daily | minute).",
    ["kind"],
)

signal_db_write_failures_total = Counter(
    "signal_db_write_failures_total",
    "Count of failed INSERT into the signals table (fire-and-forget).",
)

rate_limit_hit_total = Counter(
    "rate_limit_hit_total",
    "Count of Alpaca 429 responses observed by the signal service.",
)


METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST


def metrics_body() -> bytes:
    return generate_latest()
