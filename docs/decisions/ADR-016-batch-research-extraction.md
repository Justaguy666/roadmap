# ADR-016: Batch Evidence Extraction, Deterministic Source Selection, Rate Limiting, and Quota Awareness

## Status
Accepted

## Context
During initial end-to-end runs of the Research Agent using Google Gemini free tier (and similarly applicable to OpenAI tier limits):
1. **Request Storm & Quota Exhaustion**: A search run discovered 49 URLs and fetched 41 pages. The prior architecture performed 1 LLM extraction call per fetched page. At 41 sequential or concurrent calls against a 5-15 RPM (requests per minute) and 20 RPD (requests per day) free-tier quota, the API quota was rapidly exhausted, halting the run with only 5 sources and 27 evidence items.
2. **Unbounded Low-Value Page Analysis**: Scraping all 40+ pages wasted quota on repetitive job aggregation boards, blog duplicates, or weak sources.
3. **Metadata Mapping Discrepancy**: The CLI displayed `Target Market / Role: Game Development` instead of resolving the user's geographic target markets (`Vietnam, Japan, Western`) configured in their profile.

## Decision
1. **Deterministic Source Selection (SourceSelector)**:
   - Before fetching full page contents, rank and filter deduplicated search results.
   - Limit deep extraction to a configurable budget ROADMAP_RESEARCH_MAX_SOURCES (default 15).
   - Enforce domain diversity with max_per_domain=3 so single domains cannot monopolize analysis.
   - Combine heuristic scoring: domain authority, preliminary source type base scores, keyword alignment, and search provider relevance.

2. **Batch Evidence Extraction**:
   - Rather than 1 LLM invocation per page, pack ROADMAP_RESEARCH_BATCH_SIZE pages (default 5) into a single structured prompt (BatchEvidenceExtractionResult).
   - Bound content per page to ROADMAP_RESEARCH_MAX_CONTENT_CHARS (default 3,500 chars).
   - Reduces total extraction LLM calls from 40+ to 2-3 calls per research run (a ~90% reduction in requests).

3. **Client-Side Rate Limiter**:
   - Implement a thread-safe token bucket RateLimiter paced to ROADMAP_LLM_REQUESTS_PER_MINUTE (default 4.0 RPM for safe free-tier operations).
   - Automatically pause or respect upstream etry_after headers.

4. **Quota Awareness & Partial Status Semantics**:
   - Differentiate transient per-minute rate limits from permanent DAILY_QUOTA_EXCEEDED errors (LLMDailyQuotaExceededError).
   - If daily quota is hit, gracefully abort further extraction without retry loops, salvage all evidence and sources collected so far, and mark the run status as PARTIAL rather than crashing or claiming complete.
   - Set status to COMPLETED only if analysis completes normally, PARTIAL if quota was hit but evidence exists, and FAILED if no usable sources/evidence were obtained.

5. **Profile Target Market Mapping**:
   - oadmap research and oadmap generate resolve market priority: profile.target_markets (e.g. Vietnam, Japan, Western) -> profile.preferred_industry -> Global.
   - Include target markets in search query generation and extraction context.

## Consequences
- **Positive**:
  - Full research runs comfortably complete within free-tier quotas (typically 2-4 total LLM calls per run).
  - Search results are diversified across employers, official docs, and academic curricula.
  - Zero retry storming when daily quotas are hit; useful partial intelligence is preserved.
  - Clean CLI feedback on rate limiting, partial status, and geographic targets.
- **Negative**:
  - Pages beyond the top 15 are not deeply scraped (acceptable trade-off; market statistics remain statistically robust).
