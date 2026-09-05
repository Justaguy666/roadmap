"""
FakeWebFetcher: Deterministic web fetcher double for offline tests.
"""

from __future__ import annotations

from roadmap.application.ports.infrastructure import FetchResult, WebFetcher


class FakeWebFetcher(WebFetcher):
    """Deterministic in-memory web fetcher."""

    def __init__(self, canned_pages: dict[str, str] | None = None) -> None:
        self.canned_pages = canned_pages or {}
        self.fetched_urls: list[str] = []

    def fetch(self, url: str, timeout: int = 30) -> FetchResult:  # noqa: ARG002
        self.fetched_urls.append(url)

        if url in self.canned_pages:
            return FetchResult(
                url=url,
                content=self.canned_pages[url],
                status_code=200,
                content_type="text/html",
            )

        # Generic default mock page content
        return FetchResult(
            url=url,
            content=(
                f"<html><head><title>Sample Content for {url}</title></head>"
                "<body><h1>Core Engineering Competencies</h1>"
                "<p>Professional gameplay programming demands mastery of C++, modern engine architecture (Unreal Engine 5), "
                "data-oriented design, mathematical principles (linear algebra and 3D vectors), and multiplayer networking.</p>"
                "</body></html>"
            ),
            status_code=200,
            content_type="text/html",
        )
