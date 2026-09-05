# Research Pipeline Architecture

The RoadmapAI research pipeline transforms static roadmap generation into an **evidence-based, market-grounded intelligence workflow**.

```
Target Career & User Profile
            ↓
    [Research Planning] (LLM decomposes into targeted market & resource queries)
            ↓
      [Web Search]      (ExaSearchProvider / SearchProvider port)
            ↓
  [URL Deduplication]   (Canonical URL normalization: utm, anchors, ports stripped)
            ↓
   [Content Fetching]   (Bounded concurrency HTTP fetching with size caps & HTML stripping)
            ↓
   [Claim Extraction]   (LLM parses factual claims, related skills, confidence)
            ↓
   [Source Scoring]     (Deterministic reliability scoring based on authority, domain, age)
            ↓
 [Sample Calculation]   (Strict reporting of observed sample frequencies)
            ↓
 [Persistence & Output] (Stored in SQLite and linked to roadmap skills)
```

## Key Components

1. **Research Planner (`ResearchPlan`)**: Decomposes user goals and skill gaps into targeted search queries categorized into `market`, `resource`, or `general`.
2. **Search Provider (`SearchProvider` port)**:
   - `ExaSearchProvider`: Neural search via Exa API for high-density technical and job posting results.
   - `FakeSearchProvider`: Deterministic offline double for tests and isolated environments.
3. **Web Fetcher (`WebFetcher` port)**:
   - `HttpWebFetcher`: Fetches web content, strips unnecessary HTML boilerplate, and enforces response size limits (1.5 MB).
   - `FakeWebFetcher`: Deterministic mock response provider.
4. **Research Caching (`Cache` port)**:
   - `DiskCacheService`: On-disk key-value cache using `diskcache` with SHA-256 hashed keys and TTL to avoid redundant network calls.
5. **Deterministic Source Scorer (`SourceScorer`)**:
   - Scores sources deterministically between 0.0 and 1.0 based on `SourceType` (e.g., official docs: 0.95, university curriculum: 0.90, job postings: 0.85, blogs: 0.60), authoritative domain bonuses (+0.05), and annual freshness decay penalties.
