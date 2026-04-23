from __future__ import annotations

import io
import json
import logging

from nexusquant_signal.alpaca_logger import (
    REDACTED,
    SENSITIVE_HEADERS,
    AlpacaLogEvent,
    get_alpaca_logger,
    log_alpaca_event,
    redact_headers,
)


def test_redact_headers_none_is_empty() -> None:
    assert redact_headers(None) == {}


def test_redact_headers_passes_through_safe() -> None:
    assert redact_headers({"Content-Type": "application/json"}) == {
        "Content-Type": "application/json",
    }


def test_redact_headers_scrubs_sensitive_case_insensitive() -> None:
    out = redact_headers(
        {
            "APCA-API-KEY-ID": "PK123",
            "apca-api-secret-key": "SK456",
            "Authorization": "Bearer xyz",
            "X-Request-Id": "req-1",
        }
    )
    assert out["APCA-API-KEY-ID"] == REDACTED
    assert out["apca-api-secret-key"] == REDACTED
    assert out["Authorization"] == REDACTED
    assert out["X-Request-Id"] == "req-1"


def test_sensitive_headers_set_is_lowercase() -> None:
    for h in SENSITIVE_HEADERS:
        assert h == h.lower()


def test_event_to_dict_omits_none_optional_fields() -> None:
    e = AlpacaLogEvent(service="signal", direction="req", endpoint="/v2/stocks/bars", method="GET")
    d = e.to_dict()
    assert d["service"] == "signal"
    assert d["direction"] == "req"
    assert d["endpoint"] == "/v2/stocks/bars"
    assert d["method"] == "GET"
    assert "ts" in d
    for optional in ("status_code", "latency_ms", "request_id", "symbol", "client_order_id"):
        assert optional not in d


def test_event_to_dict_includes_populated_fields() -> None:
    e = AlpacaLogEvent(
        service="signal",
        direction="res",
        endpoint="/v2/stocks/bars",
        method="GET",
        status_code=200,
        latency_ms=42.5,
        request_id="req-abc",
        symbol="AAPL",
    )
    d = e.to_dict()
    assert d["status_code"] == 200
    assert d["latency_ms"] == 42.5
    assert d["request_id"] == "req-abc"
    assert d["symbol"] == "AAPL"


def test_log_alpaca_event_emits_one_json_line_no_secrets() -> None:
    buf = io.StringIO()
    logger = logging.getLogger("alpaca.test_signal")
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    event = AlpacaLogEvent(
        service="signal",
        direction="res",
        endpoint="/v2/stocks/bars",
        method="GET",
        status_code=200,
        latency_ms=12.3,
        symbol="AAPL",
        request_id="req-1",
    )
    log_alpaca_event(logger, event)

    line = buf.getvalue().strip()
    assert line.count("\n") == 0
    payload = json.loads(line)
    assert payload["symbol"] == "AAPL"
    assert payload["status_code"] == 200
    # no secret-like strings leak
    for forbidden in ("APCA-API-KEY-ID", "APCA-API-SECRET-KEY", "apca-api-key-id"):
        assert forbidden not in line


def test_get_alpaca_logger_is_idempotent() -> None:
    a = get_alpaca_logger("cfg_test")
    handlers_before = list(a.handlers)
    b = get_alpaca_logger("cfg_test")
    assert a is b
    assert list(b.handlers) == handlers_before
