"""
DiskCacheService: File-backed caching implementation of the Cache port.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import diskcache

from roadmap.application.ports.infrastructure import Cache
from roadmap.config.settings import settings
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class DiskCacheService(Cache):
    """
    Persistent on-disk cache using the diskcache library.
    """

    def __init__(self, cache_dir: Path | None = None, default_ttl_seconds: int = 86400) -> None:
        self.directory = cache_dir or settings.cache_dir
        self.directory.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl_seconds
        self._cache = diskcache.Cache(str(self.directory), size_limit=settings.cache_max_size_mb * 1024 * 1024)

    def get(self, key: str) -> bytes | None:
        norm_key = self._hash_key(key)
        val = self._cache.get(norm_key, default=None)
        if val is None:
            return None
        return bytes(val)

    def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        norm_key = self._hash_key(key)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._cache.set(norm_key, value, expire=ttl)

    def delete(self, key: str) -> None:
        norm_key = self._hash_key(key)
        self._cache.delete(norm_key)

    def exists(self, key: str) -> bool:
        norm_key = self._hash_key(key)
        return norm_key in self._cache

    def clear(self) -> None:
        self._cache.clear()

    @staticmethod
    def _hash_key(key: str) -> str:
        """Create safe hash key from arbitrary length string."""
        return hashlib.sha256(key.strip().lower().encode("utf-8")).hexdigest()
