"""Application ports: WebFetcher, Cache, and Clock interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


# ── WebFetcher ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FetchResult:
    """Result of fetching a URL."""

    url: str
    content: str
    status_code: int
    content_type: str = "text/html"
    fetched_at: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fetched_at", datetime.now(timezone.utc))

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


class WebFetcher(Protocol):
    """Port interface for HTTP page fetching."""

    def fetch(self, url: str, timeout: int = 30) -> FetchResult:
        """Fetch a URL and return its content."""
        ...


class FetchError(Exception):
    """Raised when a URL cannot be fetched."""


# ── Cache ─────────────────────────────────────────────────────────────────────

class Cache(Protocol):
    """Port interface for key-value caching."""

    def get(self, key: str) -> bytes | None:
        """Return cached value or None if not found / expired."""
        ...

    def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        """Store a value with an optional TTL in seconds."""
        ...

    def delete(self, key: str) -> None:
        """Remove a key from the cache."""
        ...

    def exists(self, key: str) -> bool:
        """Return True if key exists and is not expired."""
        ...

    def clear(self) -> None:
        """Remove all cached items."""
        ...


# ── Clock ─────────────────────────────────────────────────────────────────────

class Clock(Protocol):
    """Port interface for time — allows test overrides."""

    def now(self) -> datetime:
        """Return the current UTC datetime."""
        ...

    def utcnow(self) -> datetime:
        """Alias for now()."""
        ...

