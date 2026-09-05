# ADR-002 — Clean Layered Architecture with Domain Independence

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-05 |
| **Deciders** | Engineering team |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Context

Once the modular monolith decision was made (see [ADR-001](ADR-001-modular-monolith.md)), we needed to decide how the internal layers of the monolith would be structured and how dependencies between them would be managed.

### Problem

Without a clear internal structure, a growing application naturally suffers from:

- **Tight coupling between UI and business logic** — changing the output format requires touching planning code.
- **Infrastructure bleeding into the domain** — database sessions or HTTP client calls appear inside gap-analysis logic.
- **Low testability** — to test a business rule, you must spin up a database or mock an HTTP endpoint.
- **Scattered responsibilities** — it becomes unclear where a new feature should live.

### Options considered

1. **No explicit layers** — "just write code where it makes sense". Fast initially, degrades badly.
2. **Two-layer (UI + everything else)** — separates presentation but leaves business/infrastructure mixed.
3. **Three-layer (Presentation + Application + Data)** — classic n-tier; still couples business logic to persistence details.
4. **Clean/Hexagonal Architecture** — domain at the centre with no external dependencies; outer layers depend inward; ports & adapters for all external systems.

---

## Decision

We adopt a **Clean / Layered Architecture** with the following dependency rule:

```
cli  →  application  →  domain
                    ↑
             infrastructure
             (implements ports defined in domain)
```

The **dependency rule** is strict and unidirectional: inner layers **never** import from outer layers.

### Layer definitions

#### Domain (`roadmap/domain/`)
- Contains entities, value objects, domain services, and repository/provider **ports** (abstract `Protocol` interfaces).
- **Zero third-party imports.** Allowed dependencies: Python standard library only.
- This layer is the most stable; it changes only when business rules change.

#### Application (`roadmap/application/`)
- Contains use-cases that orchestrate domain objects and drive ports.
- Imports from: `domain` only.
- Owns transaction boundaries; calls ports via constructor-injected interfaces.
- Returns DTOs (plain dataclasses) to the CLI.

#### CLI (`roadmap/cli/`)
- Contains Typer command handlers and Rich-based output renderers.
- Imports from: `application` (use-cases + DTOs) and `domain` (types for display only).
- Contains **no business logic** — only I/O.

#### Infrastructure (`roadmap/infrastructure/`)
- Contains concrete adapters: SQLAlchemy repositories, OpenAI LLM client, Exa search client.
- Implements ports defined in `domain/ports/`.
- Imports from: `domain` (ports and types). Does **not** import from `application` or `cli`.
- Wired into use-cases at the composition root (CLI startup / DI container).

### Composition root

Adapters are wired together at application startup in `cli/main.py` or a dedicated `container.py`:

```python
# Composition root
db_session   = get_session()
llm          = OpenAIProvider(settings.openai_api_key)
search       = ExaSearchProvider(settings.exa_api_key)
roadmap_repo = SqlAlchemyRoadmapRepository(db_session)

use_case = GenerateRoadmapUseCase(
    roadmap_repo=roadmap_repo,
    llm=llm,
    search=search,
)
```

No use-case or domain object ever calls `OpenAIProvider()` directly — they only reference the `LLMProvider` protocol.

---

## Consequences

### Positive

- **High testability** — the domain and application layers can be tested with zero real infrastructure. All ports are trivially replaced with fakes or mocks.
- **Explicit boundaries** — a developer reading `domain/` understands business logic without needing to know about SQLAlchemy or HTTP clients.
- **Safe refactoring** — replacing the database, LLM provider, or CLI framework requires changes only in the infrastructure or CLI layer. Domain and application tests continue to pass unchanged.
- **Onboarding clarity** — new contributors have an unambiguous answer to "where does this code go?"
- **Infrastructure independence** — the same use-case code runs identically against SQLite (local) and PostgreSQL (production).
- **Future-proof** — if the CLI is extended to a REST API or web UI, only the `cli` layer is replaced; application and domain layers are reused verbatim.

### Negative

- **Boilerplate** — some simple operations require crossing multiple layers (e.g. a simple "fetch and display" still has CLI → use-case → repository). Mitigated by keeping use-cases thin where appropriate.
- **DTOs required at layer boundaries** — returning domain entities directly from use-cases to the CLI couples the CLI to domain internals. DTOs add a small translation cost.
- **Port proliferation** — every external system needs a port definition in `domain/ports/`. Currently manageable (3 ports); would grow with more integrations.
- **Learning curve** — engineers unfamiliar with clean/hexagonal architecture need orientation. Mitigated by this documentation and clear examples in the codebase.

### Rules enforced

The dependency rule is enforced through:
1. **Code review** — PRs violating import rules are rejected.
2. **`import-linter`** (optional, recommended for CI) — configured rules fail the build on violations.
3. **Convention** — infrastructure concrete classes are never imported inside `domain/` or `application/`. Only their protocol types are referenced.
