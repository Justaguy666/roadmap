"""
ExaSearchProvider: SearchProvider implementation using the Exa AI search API.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import httpx

from roadmap.application.ports.search_provider import (
    SearchProvider,
    SearchProviderError,
    SearchResponse,
    SearchResult,
)
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class ExaSearchProvider(SearchProvider):
    """
    Adapter for Exa AI neural search API (https://api.exa.ai).
    """

    BASE_URL = "https://api.exa.ai"

    def __init__(self, api_key: str, timeout_seconds: float = 30.0) -> None:
        if not api_key:
            raise ValueError("Exa API key must be provided.")
        self._api_key = api_key
        self._timeout = timeout_seconds

    def search(
        self,
        query: str,
        max_results: int = 10,
        include_full_content: bool = False,
    ) -> SearchResponse:
        """Execute a search query against Exa REST API."""
        endpoint = f"{self.BASE_URL}/search"
        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "User-Agent": "RoadmapAI/1.0",
        }
        payload = {
            "query": query,
            "numResults": min(max_results, 50),
            "useAutoprompt": True,
            "type": "neural",
            "contents": {
                "text": {"maxCharacters": 4000} if include_full_content else False,
            },
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                if response.status_code == 401:
                    raise SearchProviderError("Exa authentication failed: Invalid API key.")
                if response.status_code == 429:
                    raise SearchProviderError("Exa rate limit reached.")
                if response.status_code >= 400:
                    raise SearchProviderError(
                        f"Exa search error {response.status_code}: {response.text}"
                    )

                data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("Exa search request timed out", query=query)
            raise SearchProviderError(f"Exa search timeout: {exc}") from exc
        except httpx.RequestError as exc:
            logger.warning("Exa search network error", error=str(exc))
            raise SearchProviderError(f"Exa network error: {exc}") from exc

        results: list[SearchResult] = []
        raw_results = data.get("results", [])
        for item in raw_results:
            url = item.get("url", "")
            domain = urlparse(url).netloc
            pub_date: datetime | None = None
            raw_pub = item.get("publishedDate")
            if raw_pub:
                try:
                    pub_date = datetime.fromisoformat(raw_pub.replace("Z", "+00:00"))
                except Exception:
                    pub_date = None

            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title") or domain,
                    snippet=item.get("text") or item.get("snippet") or "",
                    published_at=pub_date,
                    domain=domain,
                    score=float(item.get("score") or 0.0),
                    content=item.get("text") or "",
                )
            )

        return SearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            provider="exa",
        )

    def search_similar(
        self,
        url: str,
        max_results: int = 5,
    ) -> SearchResponse:
        """Find pages similar to a target URL."""
        endpoint = f"{self.BASE_URL}/findSimilar"
        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "numResults": min(max_results, 25),
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise SearchProviderError(f"Exa findSimilar error: {exc}") from exc

        results = [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("title") or "",
                snippet=item.get("text") or "",
                domain=urlparse(item.get("url", "")).netloc,
                score=float(item.get("score") or 0.0),
            )
            for item in data.get("results", [])
        ]
        return SearchResponse(
            query=url,
            results=results,
            total_found=len(results),
            provider="exa",
        )
