# ADR-013: Mathematical Evidence Weighting and Divergence Detection

## Status
Accepted

## Context
Aggregating disparate web sources (official documentation, engineering blogs, job postings) requires an objective weighting model rather than unweighted LLM summarization. Additionally, caveats and ecosystem contradictions must be detected transparently.

## Decision
1. Implement deterministic weighting:
   $$\text{Weight} = \text{Reliability} \times \text{Relevance} \times \text{Confidence} \times \text{Freshness} + \text{DiversityBonus}$$
2. Implement divergence detection to flag contradictions, caveats, and prerequisites across sources.
3. Pass aggregated summaries and contradictions into the prompt context for candidate generation.

## Consequences
### Positive
- Authoritative documentation naturally outweighs unverified forum posts.
- Transparent explainability for every recommendation via `roadmap why <skill>`.

### Negative
- Weight tuning requires empirical benchmarking across various career domains.
