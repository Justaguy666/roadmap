"Web infrastructure package."

from roadmap.infrastructure.web.fake_fetcher import FakeWebFetcher
from roadmap.infrastructure.web.fetcher import HttpWebFetcher

__all__ = [
    "FakeWebFetcher",
    "HttpWebFetcher",
]
