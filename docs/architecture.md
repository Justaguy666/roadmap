# Architecture — RoadmapAI

> **Version:** 1.0  
> **Last updated:** 2026-09-05  
> **Status:** Living document

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Layered Architecture](#2-layered-architecture)
3. [Why the Domain Is Kept Free of External Dependencies](#3-why-the-domain-is-kept-free-of-external-dependencies)
4. [Data Flow Diagram](#4-data-flow-diagram)
5. [Component Descriptions](#5-component-descriptions)
6. [Key Architectural Decisions & Trade-offs](#6-key-architectural-decisions--trade-offs)
7. [Port / Adapter Pattern](#7-port--adapter-pattern)
8. [Multi-Agent Architecture (MVP-2+)](#8-multi-agent-architecture-mvp-2)

---

## 1. System Overview

**RoadmapAI** is a CLI-first learning-roadmap generator. Given a user's current skill set and a target goal (e.g. *"Become a production-ready MLOps engineer"*), it:

1. Assesses the gap between current skills and the goal.
2. Produces a directed, dependency-ordered skill graph.
3. Decomposes the graph into a time-boxed, prioritised learning plan.
4. (MVP-2+) Continuously refines the plan through a multi-agent evaluation loop backed by web search.

The system is intentionally designed as a **modular monolith** delivered through a single Python package (`roadmap`). All business logic lives in independently testable modules; the CLI and infrastructure are thin wrappers.

---

## 2. Layered Architecture

The codebase enforces a strict **dependency rule**: outer layers depend on inner layers, never the reverse.

```
┌──────────────────────────────────────────────────────┐
│                      CLI Layer                       │
│  roadmap/cli/  (Typer commands, output formatters)   │
└───────────────────────┬──────────────────────────────┘
                        │  calls
┌───────────────────────▼──────────────────────────────┐
│                 Application Layer                     │
│  roadmap/application/  (use-cases / services)        │
│  Orchestrates domain objects; owns transactions       │
└──────┬──────────────────────────────────┬────────────┘
       │ uses domain types                │ drives ports
┌──────▼──────────────┐       ┌───────────▼────────────┐
│    Domain Layer      │       │  Infrastructure Layer  │
│  roadmap/domain/     │       │  roadmap/infrastructure│
│  Entities, VOs,      │       │  DB repos, LLM client, │
│  domain services,    │       │  search client,        │
│  repository ports    │       │  config loaders        │
└─────────────────────┘       └────────────────────────┘
```

### Layer responsibilities at a glance

| Layer | Allowed imports | Forbidden imports |
|---|---|---|
| `cli` | `application`, `domain` (types only) | infrastructure internals |
| `application` | `domain` | `cli`, infrastructure concrete classes |
| `domain` | stdlib only | everything else |
| `infrastructure` | `domain` (ports & types) | `cli`, `application` |

---

## 3. Why the Domain Is Kept Free of External Dependencies

The domain layer contains the core business logic: skill graphs, gap analysis, plan generation, and invariant enforcement. Keeping it free of third-party libraries provides three concrete benefits:

### 3.1 Testability

Domain logic can be unit-tested with plain `pytest` — no database, no HTTP calls, no API keys required. Tests run in milliseconds and can be executed completely offline.

### 3.2 Replaceability

Because the domain defines *ports* (abstract interfaces) for everything external, swapping OpenAI for another LLM, or SQLite for PostgreSQL, requires changing only the infrastructure adapters. Domain tests never break during such a swap.

### 3.3 Clarity of intent

A developer reading `domain/` can understand the entire business model without needing to know how data is persisted or which AI provider is active. The domain speaks the language of *skills*, *plans*, and *roadmaps* — not SQL or HTTP.

---

## 4. Data Flow Diagram

### 4.1 Happy-path: generate a new roadmap

```
User (terminal)
      │
      │  roadmap generate --goal "MLOps engineer"
      ▼
┌─────────────────────────────────────────────────────────┐
│  CLI Layer                                               │
│  cli/commands/generate.py                               │
│  • Parses args / prompts for missing inputs              │
│  • Calls GenerateRoadmapUseCase                         │
└──────────────────────────┬──────────────────────────────┘
                           │ GenerateRoadmapCommand(goal, skills, prefs)
                           ▼
┌──────────────────────────────────────────────────────────┐
│  Application Layer                                        │
│  application/use_cases/generate_roadmap.py               │
│  1. Load user profile  ──► UserRepository (port)         │
│  2. Gap analysis       ──► GapAnalysisService (domain)   │
│  3. Build skill graph  ──► LLMProvider (port)            │
│  4. Validate DAG       ──► SkillGraphService (domain)    │
│  5. Build plan         ──► PlanningService (domain)      │
│  6. Persist roadmap    ──► RoadmapRepository (port)      │
│  7. Return RoadmapDTO  ──► CLI for rendering             │
└──────────────────────────────────────────────────────────┘
         │                 │                   │
         ▼                 ▼                   ▼
  ┌────────────┐   ┌──────────────┐   ┌───────────────┐
  │  SQLite /  │   │  OpenAI API  │   │  Exa Search   │
  │ PostgreSQL │   │  (LLM calls) │   │  (web search) │
  └────────────┘   └──────────────┘   └───────────────┘
```

### 4.2 Read-path: view an existing roadmap

```
roadmap show --id <uuid>
      │
      ▼
 CLI → ViewRoadmapUseCase → RoadmapRepository → DB → DTO → Renderer → stdout
```

---

## 5. Component Descriptions

### 5.1 CLI Layer (`roadmap/cli/`)

| Module | Purpose |
|---|---|
| `cli/main.py` | Typer app entrypoint; registers all command groups |
| `cli/commands/generate.py` | `roadmap generate` command |
| `cli/commands/show.py` | `roadmap show` command |
| `cli/commands/list_.py` | `roadmap list` command |
| `cli/commands/profile.py` | `roadmap profile` sub-commands |
| `cli/renderers/` | Rich-based table/tree/panel formatters |
| `cli/prompts.py` | Interactive prompts (Questionary wrappers) |

The CLI is responsible **only** for I/O: parsing arguments, collecting user input, and pretty-printing results. It never contains business logic.

### 5.2 Application Layer (`roadmap/application/`)

| Module | Purpose |
|---|---|
| `use_cases/generate_roadmap.py` | Orchestrates full roadmap creation |
| `use_cases/update_progress.py` | Marks milestones/skills as complete |
| `use_cases/gap_analysis.py` | Stand-alone gap report use-case |
| `use_cases/search_resources.py` | Fetches curated learning resources |
| `services/` | Cross-cutting app services (logging, event bus) |
| `dto/` | Data Transfer Objects — thin dataclasses for CLI↔use-case boundary |

Use-cases own transaction boundaries. They call domain services for pure business logic and drive repository/provider ports for side effects.

### 5.3 Domain Layer (`roadmap/domain/`)

| Module | Purpose |
|---|---|
| `entities/roadmap.py` | `Roadmap` aggregate root |
| `entities/milestone.py` | `Milestone` entity |
| `entities/skill.py` | `Skill` entity |
| `entities/user_profile.py` | `UserProfile` entity |
| `value_objects/` | `SkillLevel`, `Priority`, `Duration`, `DateRange` |
| `services/gap_analysis.py` | Pure gap-analysis logic |
| `services/skill_graph.py` | DAG construction & validation via NetworkX |
| `services/planning.py` | Milestone sequencing & time-boxing |
| `ports/llm_provider.py` | `LLMProvider` abstract protocol |
| `ports/search_provider.py` | `SearchProvider` abstract protocol |
| `ports/repositories.py` | Repository protocols for all aggregates |
| `exceptions.py` | Domain-specific exceptions |

### 5.4 Infrastructure Layer (`roadmap/infrastructure/`)

| Module | Purpose |
|---|---|
| `db/models.py` | SQLAlchemy ORM models |
| `db/session.py` | Engine / session factory |
| `db/migrations/` | Alembic migration scripts |
| `repositories/` | Concrete SQLAlchemy repository implementations |
| `llm/openai_provider.py` | OpenAI adapter (Instructor + Pydantic) |
| `search/exa_provider.py` | Exa search adapter |
| `config/settings.py` | Pydantic-Settings environment loading |

---

## 6. Key Architectural Decisions & Trade-offs

### 6.1 Modular Monolith vs. Microservices

**Decision:** Single Python package, deployed as one process.

| Trade-off | Benefit | Cost |
|---|---|---|
| Deployment | One binary/container | Cannot scale components independently |
| Dev experience | Instant local setup (`pip install -e .`) | Potential for accidental coupling if discipline lapses |
| Latency | Zero IPC overhead | All workloads share one Python GIL |
| Testing | Single test suite, shared fixtures | No forced API boundary between modules |

See [ADR-001](decisions/ADR-001-modular-monolith.md) for full rationale.

### 6.2 LLM as a Tool, Not an Architect

The system uses an LLM to *propose* structured data (skills, edges, milestones) but never trusts it for structural correctness. NetworkX validates every proposed skill graph as a valid DAG before any plan is built. This prevents hallucinated cycles from corrupting the roadmap.

### 6.3 SQLite-first with PostgreSQL upgrade path

Local installs use SQLite with WAL mode — zero configuration, single-file database. CI and production can point `DATABASE_URL` at a PostgreSQL instance. Alembic handles schema evolution for both. The `render_as_batch=True` flag makes Alembic migrations SQLite-compatible.

### 6.4 Structured LLM Outputs via Instructor

All LLM calls return validated Pydantic models via the [Instructor](https://github.com/jxnl/instructor) library. This eliminates the fragile JSON-parsing code that normally accompanies LLM integration.

---

## 7. Port / Adapter Pattern

Every external dependency (LLM, search engine, database) is hidden behind a **port** — a Python `Protocol` defined in `domain/ports/`. The infrastructure layer provides **adapters** that implement these protocols.

```
domain/ports/llm_provider.py          (Port — pure interface)
        │
        │  implements
        ▼
infrastructure/llm/openai_provider.py  (Adapter — concrete)
infrastructure/llm/mock_provider.py    (Adapter — test double)
```

Application-layer use-cases accept ports via constructor injection:

```python
class GenerateRoadmapUseCase:
    def __init__(
        self,
        roadmap_repo: RoadmapRepository,   # port
        llm: LLMProvider,                  # port
        search: SearchProvider,            # port
    ) -> None: ...
```

This makes the entire application layer trivially testable with lightweight fakes — no real network calls needed.

### Ports defined in `domain/ports/`

| Port | Methods | Notes |
|---|---|---|
| `LLMProvider` | `complete(prompt, response_model)` | Returns validated Pydantic model |
| `SearchProvider` | `search(query, n_results)` | Returns list of `SearchResult` VOs |
| `RoadmapRepository` | `save`, `get_by_id`, `list_by_user` | Aggregate-per-repo pattern |
| `UserProfileRepository` | `save`, `get_by_id` | — |
| `MilestoneRepository` | `save`, `get_by_roadmap` | — |

---

## 8. Multi-Agent Architecture (MVP-2+)

Starting in MVP-2, roadmap generation is enhanced by a **multi-agent evaluation loop**:

```
┌──────────────────────────────────────────────────────────────────┐
│  Orchestrator Agent                                               │
│  (application/agents/orchestrator.py)                            │
│  • Receives the user goal                                        │
│  • Spawns sub-agents; aggregates results                         │
└────┬───────────────┬─────────────────────┬────────────────────────┘
     │               │                     │
     ▼               ▼                     ▼
┌──────────┐  ┌──────────────┐   ┌──────────────────┐
│ Research │  │  Curriculum  │   │   Critic Agent   │
│  Agent   │  │    Agent     │   │                  │
│          │  │              │   │ Reviews draft;   │
│ Uses Exa │  │ Builds skill │   │ scores quality;  │
│ to find  │  │ graph +      │   │ emits revision   │
│ current  │  │ milestone    │   │ feedback         │
│ courses, │  │ breakdown    │   └────────┬─────────┘
│ blogs    │  └──────┬───────┘            │ feedback
└────┬─────┘         │ draft              │
     │ resources     ▼                    ▼
     └──────────► Revision Loop ◄─────────┘
                  (MAX_REVISIONS=3)
                       │ accepted plan
                       ▼
                  Final Roadmap
```

### Agent Roles

| Agent | Responsibility | LLM usage |
|---|---|---|
| **Orchestrator** | Coordinates the loop; enforces `MAX_REVISIONS` | Low (routing only) |
| **Research Agent** | Queries Exa for high-quality resources per skill | Medium (summarisation) |
| **Curriculum Agent** | Proposes skill graph + milestones | High (structured generation) |
| **Critic Agent** | Evaluates draft against quality rubric | High (reasoning) |

### Bounded Revision Loop

To prevent infinite recursion the loop is hard-capped at `MAX_REVISIONS = 3`. If the Critic has not accepted the plan by revision 3, the best-scored draft is accepted automatically and a warning is shown to the user. See [ADR-007](decisions/ADR-007-bounded-agent-loop.md).

### Agent Communication

Agents communicate through plain Python function calls and shared Pydantic DTOs — there is no message broker. The orchestrator owns the state machine, making the flow deterministic and debuggable.
