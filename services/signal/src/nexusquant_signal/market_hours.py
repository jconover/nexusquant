"""US equity regular-trading-hours helper.

09:30 - 16:00 America/New_York, Monday-Friday. Holidays are deferred to
Phase 3 when we need accurate session boundaries for live ingestion.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OPEN = time(9, 30)
CLOSE = time(16, 0)


def is_market_hours(now: datetime | None = None) -> bool:
    here = datetime.now(tz=ET) if now is None else now.astimezone(ET)
    if here.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    return OPEN <= here.time() < CLOSE
