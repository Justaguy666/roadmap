# ADR-001 — Modular Monolith Architecture

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-05 |
| **Deciders** | Engineering team |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Context

RoadmapAI is a new CLI application that helps learners generate personalised learning roadmaps. As we began the project, we needed to choose the fundamental system architecture style.

The primary options considered were:

1. **Microservices** — each capability (LLM gateway, planner, search, storage) deployed as an independent service communicating over HTTP/gRPC or a message bus.
2. **Modular Monolith** — a single deployable Python package with clearly separated internal modules, each with explicit boundaries and dependency rules.
3. **Monolith (unstructured)** — a single package with no enforced module boundaries.

### Forces at play

- The application is a **CLI tool** — it runs as a single process, invoked by one user at a time.
- There is a **small team** (1–3 engineers) with limited operational capacity.
- **Developer experience** is critical: contributors must be able to run the entire system locally with a single `pip install -e .` and no Docker Compose or running daemons.
- **Latency** between components matters for CLI responsiveness. Inter-process calls add tens of milliseconds that are perceptible to the user.
- **Testability** is a first-class requirement. All business logic must be independently testable.
- The system will grow to include multi-agent features in MVP-2, so internal structure matters.

---

## Decision

We will build RoadmapAI as a **modular monolith**.

The application is packaged and deployed as a single Python project (`roadmap`). Internal module boundaries are enforced by:

1. **Layered architecture with explicit dependency rules** (see [ADR-002](ADR-002-clean-layered-architecture.md)): `cli → application → domain`; infrastructure adapters are injected, never imported directly by the domain.
2. **Module-level `__all__` exports** defining public surfaces.
3. **Import linting** (via `import-linter` or custom checks) to prevent cross-layer violations from creeping in.
4. **Clear directory structure** that mirrors the conceptual boundaries.

The modular monolith is deliberately designed so that **individual modules could be extracted into microservices in the future** if scaling requirements demand it — but we do not build or pay for that complexity today.

---

## Consequences

### Positive

- **Zero operational overhead** — no service discovery, no API contracts between internal modules, no distributed tracing required during development.
- **Instant local setup** — a new contributor runs `pip install -e ".[dev]"` and the full application works.
- **Low latency** — all logic executes in the same process; no IPC overhead for the inner loop.
- **Simpler testing** — one test suite, shared fixtures, no integration environment needed for most tests.
- **Clear upgrade path** — well-defined module boundaries make future extraction to microservices straightforward if needed.
- **Easier debugging** — a single stack trace covers the full call path from CLI to DB.
- **Shared Pydantic models** — all modules share the same domain types without a serialisation layer between them.

### Negative

- **Coupling risk** — without discipline, the monolith can become a "big ball of mud". Mitigated by enforced layer rules and code review.
- **Single deployment unit** — cannot scale individual components (e.g. the LLM gateway) independently. Not a concern for a CLI tool.
- **One Python version / environment** — all modules must be compatible with the same Python version and dependency set. Mitigated by careful dependency management.
- **Cannot use different languages per module** — if a future capability (e.g. a high-performance graph engine) would benefit from a different runtime, it cannot be introduced without creating an external service. Accepted risk given current scope.

### Neutral

- As the team grows, stricter tooling (e.g. `import-linter` configuration files) may need to be introduced to maintain boundary discipline.
- Microservices remain an option for any component that grows to need independent scaling, but the decision to extract must be justified by concrete operational data rather than speculation.

---

## Considered Alternatives

### A. Microservices (rejected)

**Why rejected:** The application is a CLI tool with a single-user execution model. Microservices would introduce Docker Compose, service mesh configuration, distributed tracing, and serialisation overhead — all complexity with no benefit at this scale. The team is small and operational cost must remain near zero.

### B. Unstructured Monolith (rejected)

**Why rejected:** Without explicit module boundaries, a growing codebase inevitably accumulates accidental coupling. Business logic leaks into CLI handlers; infrastructure details leak into domain objects. This makes testing hard and change expensive. The modular monolith gives us the simplicity of a monolith with the maintainability of disciplined modules.
