"""
HttpWebFetcher: Production HTTP page fetcher and text extractor using httpx.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

import httpx

from roadmap.application.ports.infrastructure import FetchError, FetchResult, WebFetcher
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

# Max page size to accept (1.5 MB)
MAX_CONTENT_BYTES = 1_500_000


class HttpWebFetcher(WebFetcher):
    """
    Targeted web page fetcher for search result URLs.
    Extracts plain readable text, handles timeouts and HTTP failures gracefully.
    """

    def __init__(self, user_agent: str = "RoadmapAI-Bot/1.0 (+https://github.com/Justaguy666/roadmap)") -> None:
        self.user_agent = user_agent

    def fetch(self, url: str, timeout: int = 20) -> FetchResult:
        """Fetch page and extract readable content."""
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise FetchError(f"Invalid URL: {url!r}")

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            with httpx.Client(timeout=float(timeout), follow_redirects=True) as client:
                response = client.get(url, headers=headers)

                if len(response.content) > MAX_CONTENT_BYTES:
                    # Truncate oversized document
                    raw_text = response.content[:MAX_CONTENT_BYTES].decode("utf-8", errors="ignore")
                else:
                    raw_text = response.text

                content_type = response.headers.get("content-type", "text/html")
                readable_text = self._extract_readable_text(raw_text)

                return FetchResult(
                    url=str(response.url),
                    content=readable_text,
                    status_code=response.status_code,
                    content_type=content_type,
                )
        except httpx.TimeoutException as exc:
            logger.debug("Fetch timeout", url=url)
            raise FetchError(f"Timeout fetching {url}: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.debug("HTTP fetch error", url=url, error=str(exc))
            raise FetchError(f"HTTP error fetching {url}: {exc}") from exc
        except Exception as exc:
            logger.debug("Unexpected fetch error", url=url, error=str(exc))
            raise FetchError(f"Error fetching {url}: {exc}") from exc

    def _extract_readable_text(self, html: str) -> str:
        """Extract clean, readable text from HTML."""
        if not html:
            return ""

        # Remove scripts and styles
        text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove comments
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
        # Replace block tags with newlines
        text = re.sub(r"</?(p|div|h[1-6]|li|tr|br|section|article)[^>]*>", "\n", text, flags=re.IGNORECASE)
        # Strip all remaining tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Unescape HTML entities
        text = unescape(text)
        # Normalize whitespace
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        # Limit extracted characters to 8,000 to avoid giant prompts
        return cleaned[:8000]
