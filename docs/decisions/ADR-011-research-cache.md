# ADR-011: Persistent Disk Caching for Research Queries and Pages

## Status
Accepted

## Context
Executing repeated web searches and content fetches across LLM planning steps or repeated runs introduces significant latency, exhausts third-party rate limits, and increases API costs.

## Decision
Implement a persistent disk cache via `diskcache`:
1. Define a `Cache` port in `roadmap.application.ports.infrastructure`.
2. Implement `DiskCacheService` using `diskcache.Cache` with SHA-256 key hashing and configurable TTL (default 24 hours).
3. Cache raw search responses and fetched HTML text by canonical URL/query.
4. Allow explicit cache bypassing via the `--refresh` CLI flag.

## Consequences
- **Positive**: Sub-second repeated queries, zero network calls on cached data, reduced API bills.
- **Negative**: Cached content may become stale unless refreshed with `--refresh` or expired by TTL.
