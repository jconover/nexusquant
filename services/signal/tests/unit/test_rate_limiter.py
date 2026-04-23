from __future__ import annotations

import asyncio
import time

import pytest
from nexusquant_signal.rate_limiter import SlidingWindowRateLimiter


def test_bad_construction_raises() -> None:
    with pytest.raises(ValueError, match="max_calls"):
        SlidingWindowRateLimiter(max_calls=0)
    with pytest.raises(ValueError, match="window"):
        SlidingWindowRateLimiter(max_calls=1, window_seconds=0)


@pytest.mark.asyncio
async def test_allows_burst_up_to_max_without_delay() -> None:
    limiter = SlidingWindowRateLimiter(max_calls=5, window_seconds=60.0)
    t0 = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed < 0.05  # no blocking for first N


@pytest.mark.asyncio
async def test_blocks_on_burst_over_max() -> None:
    limiter = SlidingWindowRateLimiter(max_calls=3, window_seconds=0.2)
    # fill the window
    for _ in range(3):
        await limiter.acquire()
    t0 = time.monotonic()
    await limiter.acquire()  # must wait ~0.2s for oldest to age out
    elapsed = time.monotonic() - t0
    assert 0.15 <= elapsed <= 0.6, elapsed


@pytest.mark.asyncio
async def test_concurrent_acquirers_serialize() -> None:
    limiter = SlidingWindowRateLimiter(max_calls=2, window_seconds=0.2)

    async def worker() -> None:
        await limiter.acquire()

    t0 = time.monotonic()
    # 4 workers; first 2 run immediately, last 2 wait a window
    await asyncio.gather(*(worker() for _ in range(4)))
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.15, elapsed
