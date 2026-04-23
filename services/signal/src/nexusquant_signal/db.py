"""Postgres persistence for the signals table.

Single parameterised INSERT. Writes are scheduled as FastAPI
BackgroundTasks so the HTTP response is never blocked by the DB; a
failed write increments signal_db_write_failures_total and logs a
warning, but the handler has already returned.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from psycopg_pool import AsyncConnectionPool

from nexusquant_signal import metrics

_INSERT_SQL = (
    "INSERT INTO signals (symbol, ts, indicator_json, rule_result) VALUES (%s, %s, %s, %s)"
)


async def insert_signal(
    pool: AsyncConnectionPool,
    symbol: str,
    ts: datetime,
    indicators: dict[str, Any],
    rule_result: str,
) -> None:
    """Direct write. Raises on any DB error; callers typically catch via
    persist_signal_or_log()."""
    async with pool.connection() as conn:
        await conn.execute(
            _INSERT_SQL,
            (symbol, ts, json.dumps(indicators), rule_result.lower()),
        )


async def persist_signal_or_log(
    pool: AsyncConnectionPool,
    symbol: str,
    ts: datetime,
    indicators: dict[str, Any],
    rule_result: str,
    logger: logging.Logger,
) -> None:
    """Catches every DB error so the fire-and-forget task never raises.
    Increments signal_db_write_failures_total and logs structurally."""
    try:
        await insert_signal(pool, symbol, ts, indicators, rule_result)
    except Exception as e:
        metrics.signal_db_write_failures_total.inc()
        logger.warning(
            json.dumps(
                {
                    "event": "signal_db_write_failed",
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                separators=(",", ":"),
            )
        )
