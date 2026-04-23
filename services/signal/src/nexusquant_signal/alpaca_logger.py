"""JSON-line structured logger for Alpaca API calls.

One line per outbound request and one per inbound response. Never logs
API keys, secret keys, or auth headers -- redact_headers() scrubs them
before any emission.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any

SENSITIVE_HEADERS: frozenset[str] = frozenset(
    {
        "apca-api-key-id",
        "apca-api-secret-key",
        "authorization",
    }
)

REDACTED = "REDACTED"


def redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Lowercase-compare header names; replace values of sensitive ones with REDACTED."""
    if not headers:
        return {}
    return {k: (REDACTED if k.lower() in SENSITIVE_HEADERS else v) for k, v in headers.items()}


@dataclass(frozen=True, slots=True)
class AlpacaLogEvent:
    service: str
    direction: str  # "req" or "res"
    endpoint: str
    method: str
    status_code: int | None = None
    latency_ms: float | None = None
    request_id: str | None = None
    symbol: str | None = None
    client_order_id: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "ts": time.time(),
            "service": self.service,
            "direction": self.direction,
            "endpoint": self.endpoint,
            "method": self.method,
        }
        optional = {
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "request_id": self.request_id,
            "symbol": self.symbol,
            "client_order_id": self.client_order_id,
            "error_code": self.error_code,
        }
        base.update({k: v for k, v in optional.items() if v is not None})
        return base


def get_alpaca_logger(service: str) -> logging.Logger:
    logger = logging.getLogger(f"alpaca.{service}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_alpaca_event(logger: logging.Logger, event: AlpacaLogEvent) -> None:
    logger.info(json.dumps(event.to_dict(), separators=(",", ":")))
