"""
Thread-safe client-side RateLimiter.

Enforces requests-per-minute limits and bounds concurrency to prevent
bursting and hitting upstream API quotas.
"""

from __future__ import annotations

import threading
import time

from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token-bucket style rate limiter.
    """

    def __init__(self, requests_per_minute: float = 4.0) -> None:
        self.rpm = max(0.1, requests_per_minute)
        self.interval = 60.0 / self.rpm
        self._lock = threading.Lock()
        self._last_request_time: float = 0.0

    def acquire(self) -> None:
        """Block until the next request is permitted according to RPM settings."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.interval:
                sleep_time = self.interval - elapsed
                logger.debug(
                    "RateLimiter pacing request",
                    sleep_seconds=round(sleep_time, 2),
                    rpm=self.rpm,
                )
                time.sleep(sleep_time)
            self._last_request_time = time.monotonic()

    def wait_for(self, seconds: float) -> None:
        """Explicit pause (e.g. following an upstream Retry-After instruction)."""
        if seconds <= 0:
            return
        logger.info("RateLimiter applying upstream retry delay", delay_seconds=round(seconds, 2))
        time.sleep(seconds)
        with self._lock:
            self._last_request_time = time.monotonic()
