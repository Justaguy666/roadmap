# ADR-006 — Deterministic Skill Graph Validation

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-05 |
| **Deciders** | Engineering team |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Context

The skill dependency graph is a Directed Acyclic Graph (DAG). Its structural correctness is critical: if the graph contains a **cycle**, the downstream planning service will loop indefinitely (or produce an undefined topological order), and the generated roadmap will be invalid.

### The problem with trusting the LLM for graph structure

Large Language Models are excellent at generating plausible, semantically rich skill lists and proposing dependency relationships. However, they are not reliable at guaranteeing structural properties of graphs:

1. **Hallucinated cycles** — An LLM may propose *"Docker → Kubernetes → Container Orchestration → Docker"* (a cycle), especially in complex domains with many related skills.
2. **Non-determinism** — The same prompt with temperature > 0 may produce a valid graph one run and a cyclic graph the next.
3. **No formal reasoning** — LLMs reason probabilistically, not formally. They cannot reliably verify that a graph is acyclic by inspection.
4. **Scale failures** — Cycle detection is provably hard for human inspection at 20+ nodes. LLMs show the same degradation.

This was observed empirically during early prototyping: GPT-4o introduced cycles in approximately 15% of skill graphs generated for complex domains (ML, Cloud, Full-Stack) when not explicitly constrained.

### Why not fix this with better prompting?

Prompt engineering can reduce cycle frequency but cannot eliminate it. Even with a chain-of-thought prompt asking the model to "verify there are no cycles", the model may hallucinate a verification that is incorrect. Prompt improvements are applied as a defence-in-depth measure, not as the primary safety mechanism.

---

## Decision

**The LLM proposes skill nodes and edges; Python/NetworkX validates structural correctness.** The LLM is never trusted to produce a cycle-free graph without independent validation.

### Trust model

```
LLM Output (untrusted)         Python (trusted validator)
────────────────────────       ────────────────────────────
list[SkillProposal]       →    SkillGraphService.build_graph()
  - name                  →    nx.DiGraph construction
  - description           →    SkillGraphService.validate_dag()
  - prerequisites: [...]  →    nx.is_directed_acyclic_graph()
                          →    if False: raise CycleDetectedError
                          →    if True: return validated SkillGraph
```

### `SkillGraphService` implementation

```python
# domain/services/skill_graph.py
import networkx as nx
from roadmap.domain.exceptions import CycleDetectedError, DuplicateSkillError

class SkillGraphService:

    def build_graph(self, skills: list[Skill]) -> nx.DiGraph:
        """
        Construct a NetworkX DiGraph from a list of Skill entities.
        Raises DuplicateSkillError if two skills share the same name.
        """
        graph = nx.DiGraph()
        seen_names: set[str] = set()

        for skill in skills:
            if skill.name.lower() in seen_names:
                raise DuplicateSkillError(skill.name)
            seen_names.add(skill.name.lower())
            graph.add_node(skill.id, skill=skill)

        for skill in skills:
            for prereq_id in skill.prerequisites:
                graph.add_edge(prereq_id, skill.id)

        return graph

    def validate_dag(self, graph: nx.DiGraph) -> None:
        """
        Raises CycleDetectedError if the graph contains a cycle.
        This is the authoritative validation gate — no plan is built
        until this check passes.
        """
        if not nx.is_directed_acyclic_graph(graph):
            cycles = list(nx.simple_cycles(graph))
            raise CycleDetectedError(
                f"Skill graph contains {len(cycles)} cycle(s): {cycles}"
            )

    def topological_order(self, graph: nx.DiGraph) -> list[UUID]:
        """Return skill IDs in a valid learning sequence."""
        return list(nx.topological_sort(graph))

    def get_prerequisites(self, graph: nx.DiGraph, skill_id: UUID) -> set[UUID]:
        """Return all transitive prerequisites for a skill."""
        return nx.ancestors(graph, skill_id)

    def get_dependents(self, graph: nx.DiGraph, skill_id: UUID) -> set[UUID]:
        """Return all skills that directly or transitively depend on this skill."""
        return nx.descendants(graph, skill_id)
```

### Recovery strategy when a cycle is detected

When `CycleDetectedError` is raised:

1. **MVP-1:** The system re-prompts the LLM with the cycle included in the error context: *"Your proposed graph contains a cycle: [A → B → C → A]. Please revise the prerequisite edges to eliminate this cycle."* Up to `MAX_REVISIONS = 3` retries are attempted.
2. **MVP-2+ (multi-agent):** The Critic Agent receives the `CycleDetectedError` as feedback and instructs the Curriculum Agent to revise the graph. The bounded revision loop (ADR-007) applies.
3. **If all retries fail:** The system raises a user-visible error with guidance to simplify the learning goal or report a bug.

### Topological sort as ground truth for ordering

Once the graph is validated as a DAG, `nx.topological_sort()` is the **sole authority** on skill learning order. The LLM is not asked to suggest an ordering — it is derived deterministically from the validated graph structure.

---

## Consequences

### Positive

- **Correctness guarantee** — `nx.is_directed_acyclic_graph()` is an O(V + E) deterministic algorithm. If it passes, the topological sort is guaranteed to succeed and produce a valid learning sequence.
- **Fast validation** — For typical skill graphs (20–100 nodes), validation runs in microseconds.
- **Clear error messages** — `nx.simple_cycles()` identifies the exact cycle(s), enabling targeted recovery prompts to the LLM.
- **Deterministic planning** — Two identical skill graphs always produce the same topological order (ties broken alphabetically). This makes roadmap generation reproducible.
- **Separation of concerns** — The LLM focuses on semantic quality (are these the right skills?); Python enforces structural integrity (is the graph valid?). Neither is asked to do the other's job.

### Negative

- **NetworkX dependency** — adds `networkx` to the domain's transitive dependencies. However, NetworkX is a pure Python library with no external dependencies of its own, making it acceptable in the domain layer as a graph algorithm utility. It is treated as "infrastructure" for graph math, analogous to how `datetime` is used for time math.

  > **Note:** If the strict "zero third-party deps in domain" rule is applied in the future, `SkillGraphService` can be moved to the application layer and NetworkX used there instead. The port/adapter for the graph service would then be defined in the domain. Currently, the convenience of keeping graph logic co-located with domain types outweighs this concern.

- **Retry latency** — if the LLM produces a cyclic graph, each retry adds an API round-trip (~2–10 s). With `MAX_REVISIONS = 3`, worst-case recovery adds ~30 s. Acceptable for a CLI workflow.

- **LLM prompt complexity increases** — to reduce cycle frequency (and thus retry cost), the system prompt for skill graph generation must include explicit instructions to avoid cycles, include example DAG structures, and request the model to verify prerequisite direction before responding. This is maintained as a prompt engineering concern, not an architectural one.

### Invariant statement

> The `SkillGraph` object returned by `SkillGraphService.build_graph()` after `validate_dag()` passes is **always a valid DAG**. Any code that holds a reference to a `SkillGraph` object may assume this invariant without re-checking.
