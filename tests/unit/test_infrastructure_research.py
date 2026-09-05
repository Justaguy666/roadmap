"""Tests for FakeSearchProvider, FakeWebFetcher, and DiskCacheService."""

from roadmap.infrastructure.cache.disk_cache import DiskCacheService
from roadmap.infrastructure.search.fake_provider import FakeSearchProvider
from roadmap.infrastructure.web.fake_fetcher import FakeWebFetcher


def test_fake_search_provider_returns_results() -> None:
    provider = FakeSearchProvider()
    res = provider.search("python rust systems programming", max_results=3)
    assert len(res.results) >= 1
    assert any("python" in r.url.lower() or "rust" in r.url.lower() or "docs" in r.url.lower() for r in res.results)


def test_fake_web_fetcher_fetches_content() -> None:
    fetcher = FakeWebFetcher()
    res = fetcher.fetch("https://docs.python.org/3/tutorial")
    assert res.is_success
    assert "Engineering" in res.content
    assert res.status_code == 200


def test_disk_cache_service_set_get_and_clear(tmp_path) -> None:
    cache = DiskCacheService(cache_dir=tmp_path / "cache", default_ttl_seconds=3600)
    val = b'{"title": "Python Docs"}'

    assert cache.get("test_key") is None
    cache.set("test_key", val)
    assert cache.get("test_key") == val

    cache.delete("test_key")
    assert cache.get("test_key") is None
