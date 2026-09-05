# ADR-004 — Search Provider Abstraction

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-05 |
| **Deciders** | Engineering team |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Context

The Research Agent (MVP-2+) must find **current, high-quality learning resources** for each skill in a roadmap — courses, articles, documentation, and tutorials. This requires a web search capability beyond what an LLM can provide from its training data.

### Why not just use the LLM's training data?

LLM training data is static and stale by definition. A model trained in early 2024 cannot:

- Know about a course released in late 2024.
- Know the current pricing or availability of a platform.
- Distinguish between a deprecated tutorial and a current one.
- Verify that a linked resource still exists.

Live web search solves all four problems.

### Search provider options considered

| Provider | Notes |
|---|---|
| **Exa** | Purpose-built for AI/research workloads; semantic search + neural ranking; returns full-page content; excellent precision for technical queries |
| **Brave Search API** | Independent index; good privacy story; less tuned for research-grade results |
| **Serper (Google wrapper)** | Fast, familiar results; subject to Google's API pricing and ToS changes |
| **Tavily** | AI-focused search; designed for agent workloads; another strong contender |
| **SerpAPI** | Aggregates multiple search engines; higher cost; many features not needed |
| **Bing Search API** | Reliable; Microsoft commercial dependency; less semantic precision for technical queries |

### Why Exa?

Exa is specifically designed for AI agents and research workloads. Key differentiators:

1. **Semantic / neural search** — queries like *"best practical Docker networking tutorial 2025"* return semantically relevant results, not just keyword-matching pages.
2. **Full-page content retrieval** — Exa can return the full cleaned text of a page alongside the URL, enabling the LLM to summarise or validate resources without a separate scraping step.
3. **High precision for technical content** — Exa's index is biased toward high-quality technical content (blog posts, docs, tutorials) rather than SEO-spam pages.
4. **Consistent API** — clean JSON responses with title, URL, snippet, and score that map directly to our `SearchResult` value object.
5. **Agent-friendly pricing** — per-query pricing with reasonable free tier for development.

---

## Decision

We define a `SearchProvider` **Protocol** in `domain/ports/search_provider.py`. Exa is the initial concrete adapter in `infrastructure/search/exa_provider.py`.

### Protocol definition

```python
# domain/ports/search_provider.py
from typing import Protocol
from roadmap.domain.value_objects.search_result import SearchResult

class SearchProvider(Protocol):
    """Abstract interface for web search capabilities."""

    def search(
        self,
        query: str,
        *,
        n_results: int = 5,
        include_full_content: bool = False,
    ) -> list[SearchResult]:
        """
        Search the web for the given query.

        Args:
            query: Natural language search query.
            n_results: Maximum number of results to return.
            include_full_content: If True, attempt to return full page text.

        Returns:
            Ordered list of SearchResult value objects (best match first).

        Raises:
            SearchError: On provider failure or rate limiting.
        """
        ...
```

### `SearchResult` value object

```python
# domain/value_objects/search_result.py
from dataclasses import dataclass

@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    score: float              # provider-assigned relevance (0.0–1.0)
    full_content: str | None  # populated when include_full_content=True
```

### Exa adapter

```python
# infrastructure/search/exa_provider.py
from exa_py import Exa
from roadmap.domain.ports.search_provider import SearchProvider
from roadmap.domain.value_objects.search_result import SearchResult

class ExaSearchProvider:
    def __init__(self, api_key: str) -> None:
        self._client = Exa(api_key=api_key)

    def search(
        self,
        query: str,
        *,
        n_results: int = 5,
        include_full_content: bool = False,
    ) -> list[SearchResult]:
        kwargs = {"num_results": n_results, "use_autoprompt": True}
        if include_full_content:
            kwargs["text"] = True

        response = self._client.search_and_contents(query, **kwargs)

        return [
            SearchResult(
                title=r.title or "",
                url=r.url,
                snippet=r.text[:500] if r.text else (r.highlights[0] if r.highlights else ""),
                score=r.score or 0.0,
                full_content=r.text if include_full_content else None,
            )
            for r in response.results
        ]
```

### Test double

```python
# tests/fakes/fake_search_provider.py
class FakeSearchProvider:
    """Returns pre-configured results for testing. No network calls."""

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or []

    def search(self, query: str, *, n_results: int = 5, **_) -> list[SearchResult]:
        return self._results[:n_results]
```

---

## Consequences

### Positive

- **High-quality resources** — Exa's semantic ranking returns results that are genuinely relevant to technical learning queries, not SEO-spam pages.
- **Provider independence** — switching to Tavily, Brave, or any other provider requires only a new infrastructure adapter; no application or domain code changes.
- **Full-content support** — the `include_full_content` flag enables the Research Agent to read page text directly, avoiding a separate scraping dependency.
- **Testability** — `FakeSearchProvider` enables Research Agent tests to run without network access.
- **Semantic queries** — Exa's neural search handles natural-language research queries better than keyword-based alternatives.

### Negative

- **API key required** — Exa requires an account and API key. The `EXA_API_KEY` env var must be set for the Research Agent to function. If it is absent, the agent gracefully degrades by returning fewer resources with a warning.
- **Cost per query** — Exa charges per search request. Research-heavy agent loops (MVP-2+) may generate 10–20 queries per roadmap. At scale this needs monitoring. Mitigated by caching frequent queries (future work).
- **Exa is a startup** — lower bus-factor risk than Google or Bing. The `SearchProvider` abstraction means we can migrate to another provider in a single PR if needed.
- **Full-content requests are slower** — fetching full page text adds latency (~1–2 s per result). The `include_full_content` flag defaults to `False` to keep the common path fast.

### Alternatives kept in mind

- **Tavily** — strong alternative; similar AI-agent focus; easy to add as a second adapter.
- **Brave Search API** — good privacy story; a reasonable fallback if Exa becomes unavailable.

Adding a second adapter (e.g. `TavilySearchProvider`) for A/B testing or fallback is a future option enabled by the protocol abstraction.
