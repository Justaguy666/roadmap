"""
Application ports: SearchProvider interface.

Exa is the initial implementation; the domain depends only on this protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    """A single result from a search query."""

    url: str
    title: str
    snippet: str
    published_at: datetime | None = None
    domain: str = ""
    score: float = 0.0                # relevance score from the provider
    content: str = ""                 # full page content if available


@dataclass
class SearchResponse:
    """Complete response from a search query."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    total_found: int = 0
    provider: str = ""


class SearchProvider(Protocol):
    """
    Port interface for web search providers.

    Initial implementation: Exa
    Alternative: Tavily, Serper, DuckDuckGo
    """

    def search(
        self,
        query: str,
        max_results: int = 10,
        include_full_content: bool = False,
    ) -> SearchResponse:
        """
        Execute a search query.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return.
            include_full_content: If True, fetch and include full page content.

        Returns:
            SearchResponse with results.
        """
        ...

    def search_similar(
        self,
        url: str,
        max_results: int = 5,
    ) -> SearchResponse:
        """Find pages similar to the given URL (if supported by provider)."""
        ...


class SearchProviderError(Exception):
    """Raised when the search provider cannot complete a request."""
