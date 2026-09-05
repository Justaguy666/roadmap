"""
Unit tests for RateLimiter and quota-handling.
"""

from __future__ import annotations

import time

from roadmap.infrastructure.llm.rate_limiter import RateLimiter


def test_rate_limiter_interval_spacing() -> None:
    # 120 RPM -> 0.5s interval
    limiter = RateLimiter(requests_per_minute=120.0)

    start = time.monotonic()
    limiter.acquire()
    limiter.acquire()
    elapsed = time.monotonic() - start

    # Should have waited approximately 0.5 seconds between 2 requests
    assert elapsed >= 0.45


def test_rate_limiter_wait_for() -> None:
    limiter = RateLimiter(requests_per_minute=60.0)
    start = time.monotonic()
    limiter.wait_for(0.2)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.18
