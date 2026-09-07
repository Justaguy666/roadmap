# ADR-022: API Foundation (FastAPI Adapter + Application Use Case Boundary)

**Status:** Accepted  
**Date:** 2026-09-08  
**Author:** RoadmapAI Engineering  
**Deciders:** Engineering Team  

---

## Context

RoadmapAI completed MVP-1 through MVP-7.1 as a modular monolith accessed primarily via Typer CLI commands. With the database layer hardened and repository boundaries cleanly decoupled into Protocol ports in MVP-7.1, the application required a production-ready HTTP API adapter.

The goal of MVP-7.2 is to establish this API foundation while preserving core architectural invariants:
1. The API must remain a thin adapter layer over existing Application Use Cases.
2. Route handlers must not depend directly on SQLAlchemy models or concrete infrastructure repositories.
3. No duplication of business logic from the CLI.
4. Existing SQLite databases must remain untouched by API tests.
5. All domain safeguards (deterministic DAG validation, anti-oscillation guards, evidence provenance, budget limits) must remain strictly enforced.
6. Authentication is explicitly deferred to MVP-7.3.

---

## Decision

### 1. Architectural Role: Thin Adapter Layer

The API is structured strictly as an inbound adapter in hexagonal/clean architecture:

```
HTTP Request
     │
     ▼
FastAPI Route Handler (`api/routers/`)
     │  - validates input via Pydantic Schemas (`api/schemas/`)
     │  - depends on Application Use Cases via FastAPI `Depends()`
     ▼
Application Use Case (`application/use_cases/`, `application/services/`)
     │  - executes business orchestration
     │  - coordinates Domain Services & Entities
     ▼
Domain Layer (`domain/`)
     │  - enforces invariants (DAG cycle checks, bounds, statuses)
     ▼
Repository Ports (`application/ports/repositories.py`)
     │  - structural typing Protocols
     ▼
Infrastructure (`storage/repositories/`)
```

Route handlers never call SQLAlchemy sessions or query ORM models directly. Query use cases (`ListRoadmapsUseCase`, `GetLatestRoadmapUseCase`, `GetRoadmapByVersionUseCase`, `ListProgressUseCase`) were introduced in the application layer to maintain this separation for read operations.

### 2. Single Canonical ASGI Application

`roadmap.api.main:app` is the single canonical ASGI application object.

The CLI command `roadmap api` (`src/roadmap/main.py`) launches this exact ASGI object via `uvicorn.run("roadmap.api.main:app", ...)`. There is no secondary initialization or duplicate configuration path.

### 3. Request-Scoped Dependency Injection

FastAPI's `Depends()` mechanism is used to manage lifecycle and injection in `src/roadmap/api/dependencies.py`:
- `get_db_session()`: Generator yielding a request-scoped SQLAlchemy `Session`. Automatically commits on successful response, rolls back on uncaught exception, and always closes in a `finally` block.
- Reuses the singleton engine from `storage/database.py` — never creates a second engine.
- Providers wire repository implementations into application use cases, which are then injected into route functions.

### 4. Canonical Error Contract

All error responses adhere to a stable, machine-readable envelope:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description"
  }
}
```

Domain exceptions are mapped deterministically:
- `ProfileNotFoundError` → 404 `PROFILE_NOT_FOUND`
- `ProfileAlreadyExistsError` → 409 `PROFILE_ALREADY_EXISTS`
- `RoadmapNotFoundError` → 404 `ROADMAP_NOT_FOUND`
- `SkillNotFoundError` → 400 `SKILL_NOT_FOUND`
- `InvalidProgressError` → 400 `INVALID_PROGRESS`
- `ValidationError` → 400 `VALIDATION_ERROR`
- `RequestValidationError` → 422 `VALIDATION_ERROR`
- Anti-oscillation guard blocks → 409 `ANTI_OSCILLATION_BLOCKED`
- Unhandled internal exceptions → 500 `INTERNAL_ERROR` (no stack traces, SQL strings, or file paths exposed)

### 5. Deferral of Authentication to MVP-7.3

Authentication and authorization are deliberately deferred to MVP-7.3. No dummy or incomplete authentication is introduced in MVP-7.2. All endpoints are currently unauthenticated, which is explicitly noted in OpenAPI schemas, route docstrings, and documentation.

### 6. Config-Driven CORS & Security

CORS middleware is conditionally applied based on `ROADMAP_API_CORS_ORIGINS`. If empty (default), CORS is disabled. Wildcard origins (`*`) with `allow_credentials=True` are explicitly prevented.

Every request receives a structured log with `request_id` (propagated or generated as UUID4) via `RequestLoggingMiddleware`. Sensitive fields (passwords, tokens, request bodies) are never logged.

### 7. Read-Only Adaptation Proposals

The adaptation endpoint `POST /api/v1/profiles/{id}/adaptations/prepare` only prepares proposals via `AdaptRoadmapUseCase.prepare_adaptation()`. It does **not** persist candidate roadmaps or overwrite active versions. Persistence remains an explicit human-in-the-loop action.

### 8. Knowledge Retrieval Provenance

`GET /api/v1/profiles/{id}/knowledge/search` delegates to `RAGService.retrieve_context()`. Results return canonical evidence blocks preserving `evidence_id`, `source_id`, `source_url`, and `is_authoritative`. Vector similarity is treated as a candidate selection mechanism, not as ground truth.

### 9. Test Isolation & Preservation of Production DB

API tests use an in-memory SQLite database (`sqlite:///:memory:`) configured with `StaticPool` to ensure cross-request connection consistency without writing to disk. An autouse fixture isolates `settings.database_url` and calls `reset_engine()` to ensure `%USERPROFILE%\.roadmap\roadmap.db` is never touched during automated testing.

---

## Consequences

### Positive
- Strict adherence to Clean/Layered Architecture: API is completely decoupled from persistence details.
- Consistent, predictable error responses for API consumers.
- Complete parity between CLI and API capabilities via shared Application Use Cases.
- Fast, reliable integration test suite (34 tests run in ~3 seconds) with zero side effects on production data.

### Negative / Trade-offs
- Read queries require dedicated application use cases rather than inline ORM queries in route functions.
- Endpoints currently operate under single-user profile semantics until multi-tenancy and authentication are introduced in MVP-7.3.
