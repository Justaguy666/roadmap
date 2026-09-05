# ADR-012: Deterministic Skill Graph (DAG) with NetworkX

## Status
Accepted

## Context
Skill prerequisites must form a strict Directed Acyclic Graph (DAG) to prevent circular dependency deadlocks and ensure sound educational progression. Relying solely on LLMs to guarantee acyclic graphs is unsafe because generative models can easily introduce subtle cycles or dangling nodes.

## Decision
1. Domain entities (`SkillNode`, `SkillDependency`) remain pure Pydantic models with zero graph library dependencies.
2. `NetworkX` is strictly isolated inside `src/roadmap/application/graph/`.
3. Validation checks acyclicity, self-dependencies, unknown nodes, and generates topological sort order and depths.
4. If cycles are detected, candidate plans are rejected and returned for revision.

## Consequences
### Positive
- 100% mathematical guarantee of acyclicity.
- Clear separation of concerns between domain and graph algorithms.
- Easy to render hierarchical tree views in CLI (`roadmap graph`).

### Negative
- Requires a graph dependency (`networkx`) in application layer.
