# ADR-009: Exa Search Provider for Deep Market Research

## Status
Accepted

## Context
A key value proposition of RoadmapAI is grounding learning paths in real-world market intelligence and canonical documentation rather than static model weights. General search APIs often return noise, SEO spam, or consumer pages, whereas technical roadmaps require high-density engineering postings, official specs, and academic syllabi.

## Decision
Adopt **Exa** as the initial live search provider for the `SearchProvider` port, with the following design:
1. Define a domain-level `SearchProvider` port returning normalized `SearchResult` and `SearchResponse` objects.
2. Implement `ExaSearchProvider` using Exa's REST API (`https://api.exa.ai/search`).
3. Provide `FakeSearchProvider` for offline test suites, local development, and environments without an `EXA_API_KEY`.
4. Configure provider selection dynamically via `settings.search_provider` (`exa` vs. `mock`/`fake`).

## Consequences
- **Positive**: High relevance on technical search queries; clean separation between application domain logic and third-party search APIs.
- **Negative**: Requires an `EXA_API_KEY` for live web searches; rate limits and usage costs must be managed with caching.
