# Skill Graph Architecture & Validation

## Overview

The Skill Graph component transforms flat skill recommendations and prerequisite relationships into a formal **Directed Acyclic Graph (DAG)**. 

To maintain strict domain isolation and deterministic guarantees:
1. **Domain Isolation**: Domain entities (`SkillNode`, `SkillDependency`) remain pure Pydantic models containing no graph library dependencies.
2. **Deterministic Validation**: `NetworkX` is strictly contained within `src/roadmap/application/graph/`. The LLM may suggest relationships, but the DAG is deterministically validated and ordered in Python.

---

## Graph Model & Normalization

### 1. SkillNode
Represents an individual node in the graph:
- `name`: Normalized canonical skill name (case-insensitive deduplication).
- `category`: Skill taxonomy bucket.
- `priority`: Priority level (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- `estimated_hours`: Estimated study time.
- `prerequisites`: List of prerequisite skill names.
- `evidence_ids`: Citations anchoring this skill to observed industry or educational sources.
- `depth`: Longest path length from root prerequisites (depth = 0).

### 2. SkillDependency
Represents directed edges:
- `prerequisite_skill` (`from_name`): The prerequisite required first.
- `dependent_skill` (`to_name`): The skill that depends on the prerequisite.
- `dependency_type`: `PREREQUISITE`, `COMPLEMENTARY`, `SPECIALIZATION`.
- `is_hard_requirement`: True if prerequisite is strictly required.

---

## Validation Engine (`SkillGraphValidator`)

Validation runs deterministically before a candidate roadmap is finalized:
- **Cycle Detection**: Cycles are detected using `nx.simple_cycles`. Any cycle invalidates the candidate and triggers repair or revision.
- **Self-Dependency Check**: Skills depending on themselves (`A -> A`) are detected and rejected.
- **Dangling / Unknown Prerequisite Detection**: Dependencies referencing skills absent from the candidate pool are recorded as errors.
- **Topological Sorting**: `nx.topological_sort` generates a strictly valid linear progression order for phases and milestones.
- **Topological Depth Assignment**: Depth is computed as the longest simple path from any root prerequisite ($d=0$) to the target node.
