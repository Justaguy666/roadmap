# ADR-014: Evaluator Agent and Bounded Revision Loop

## Status
Accepted

## Context
A single-pass LLM roadmap generation often suffers from pacing issues, timeline infeasibility, or missed prerequisite alignment. However, an unbounded multi-agent critique loop can result in infinite loops, high API costs, or latency degradation.

## Decision
1. Introduce an adversarial `RoadmapEvaluator` agent equipped with structured evaluation schemas (`EvaluationIssue`, `RoadmapEvaluationResult`).
2. Implement a `RoadmapRevisionLoop` combining deterministic DAG checks and Evaluator critique.
3. Cap the feedback loop at $\text{MAX\_ITERATIONS} = 3$.
4. Score every accepted roadmap across 7 objective dimensions with `QualityScorer`.

## Consequences
### Positive
- Robust quality gate catching edge cases prior to persistence.
- Bounded runtime guarantees cost predictability and prevents deadlocks.

### Negative
- Multi-pass generation increases token usage and latency when revisions are required.
