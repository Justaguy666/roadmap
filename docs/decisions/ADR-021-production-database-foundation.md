# ADR-021: Production Database Foundation

**Status:** Accepted  
**Date:** 2026-09-07  
**Author:** RoadmapAI Engineering  
**Deciders:** Engineering Team  

---

## Context

RoadmapAI reached MVP-6 with a clean layered architecture (Domain → Application → Infrastructure),
SQLAlchemy 2.0 ORM, and SQLite as the default persistence backend.

Before moving toward production deployment, three structural problems had to be resolved:

1. **Missing Alembic migration chain** — 13 core domain tables were created by `Base.metadata.create_all()`
   before Alembic was adopted. Migration `881408fd6535` (the former chain root) had `down_revision = None`
   but only created 2 tables (`llm_provider_states`, `llm_usage_records`). A fresh `alembic upgrade head`
   on an empty database would crash at `1b315108acef` with `OperationalError: no such table: roadmaps`.

2. **Application-layer leakage** — 7 files in `application/use_cases/` and `application/services/`
   imported concrete `Sqlite*Repository` classes directly. This violated the Clean Architecture boundary;
   the application layer must depend only on *port abstractions*, not on specific storage implementations.

3. **SQLite-only engine configuration** — `database.py` had no PostgreSQL pool settings, and `env.py`
   unconditionally applied `render_as_batch=True` (a SQLite-only workaround) even in PostgreSQL mode.

---

## Decision

### 1. Alembic Baseline Migration (`0001_baseline_schema`)

Created `migrations/versions/0001_baseline_schema.py` as the new Alembic chain root
(`down_revision = None`). It materialises all 13 pre-Alembic core domain tables:

| # | Table | Source model |
|---|-------|-------------|
| 1 | `user_profiles` | `UserProfileModel` |
| 2 | `skills` | `SkillModel` |
| 3 | `skill_dependencies` | `SkillDependencyModel` |
| 4 | `roadmaps` | `RoadmapModel` (without `validation_status`, `evaluator_*` — added by `1b315108acef`) |
| 5 | `roadmap_phases` | `RoadmapPhaseModel` |
| 6 | `milestones` | `MilestoneModel` |
| 7 | `learning_resources` | `LearningResourceModel` |
| 8 | `projects` | `ProjectModel` |
| 9 | `sources` | `SourceModel` |
| 10 | `evidence` | `EvidenceModel` |
| 11 | `research_runs` | `ResearchRunModel` |
| 12 | `recommendations` | `RecommendationModel` |
| 13 | `progress_records` | `ProgressRecordModel` (without `phase_id`, `status`, `planned_hours`, `actual_hours`, `started_at` — added by `aaa1f04d5354`) |

**Idempotency**: The upgrade function uses `sqlalchemy.inspect` to check whether each table already
exists before issuing `CREATE TABLE`. Existing databases at `94579f682a90` (head) are unaffected.

**Migration chain (corrected)**:

```
0001_baseline_schema
  └─ 881408fd6535  (llm_provider_states, llm_usage_records)
       └─ 1b315108acef  (roadmaps: +validation_status, +evaluator_score, +evaluator_verdict)
            └─ aaa1f04d5354  (learning_feedbacks, roadmap_adaptations; progress_records: +phase_id, +status, +planned_hours, +actual_hours, +started_at)
                 └─ 94579f682a90  (knowledge_documents, knowledge_chunks, embedding_records)  ← HEAD
```

### 2. Application Layer Port Boundary

All imports of `Sqlite*Repository` classes were removed from:

- `application/use_cases/record_progress.py` → uses `ProgressRepository`, `RoadmapRepository`, `FeedbackRepository`
- `application/use_cases/record_feedback.py` → uses `RoadmapRepository`, `FeedbackRepository`
- `application/use_cases/adapt_roadmap.py` → uses `RoadmapRepository`, `ProgressRepository`, `FeedbackRepository`, `AdaptationRepository`
- `application/services/knowledge_indexing_service.py` → uses `EvidenceRepository`, `SourceRepository`, `KnowledgeRepository`
- `application/services/semantic_retrieval_service.py` → uses `EvidenceRepository`, `SourceRepository`
- `application/services/context_builder.py` → uses `EvidenceRepository`, `SourceRepository`
- `application/services/research_service.py` → uses `SourceRepository`, `EvidenceRepository`, `ResearchRunRepository`

All protocol types are defined in `application/ports/repositories.py`. Python's `Protocol` is structural
(duck-typing), so the concrete `Sqlite*Repository` classes satisfy these interfaces without modification.

### 3. Dialect-Aware Engine & Migration Configuration

**`storage/database.py`**:
- SQLite engine: `check_same_thread=False`, WAL mode pragmas, `NullPool`.
- PostgreSQL engine: `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, `pool_pre_ping=True`.
- `reset_engine()` function added for clean teardown in tests.

**`migrations/env.py`**:
- `render_as_batch` is now conditional:
  - Offline mode: `is_sqlite = url.startswith("sqlite")`
  - Online mode: `is_sqlite = connection.dialect.name == "sqlite"`
- PostgreSQL migrations will use standard DDL (no batch mode workaround).

**`config/settings.py`**:
- Added `db_pool_size`, `db_max_overflow`, `db_pool_timeout`, `db_pool_recycle` settings.
- `resolved_database_url` normalises `postgresql://` and `postgres://` to `postgresql+psycopg://`.
- `is_sqlite` and `is_postgres` properties for dialect detection.

**`storage/models/progress_model.py`**:
- `SourceModel.url` changed from `Text` to `String(2048)` — PostgreSQL requires bounded types for UNIQUE constraints.

**`storage/models/user_profile_model.py`**:
- Added explicit `Float` and `Integer` SA column types to `study_hours_per_day` and `deadline_months`.

### 4. PostgreSQL Driver

Added `psycopg[binary]>=3.1.18` as a production dependency. This provides the `postgresql+psycopg://`
dialect adapter for SQLAlchemy 2.0. No PostgreSQL instance is required for local development or tests —
SQLite remains the default and the psycopg offline DDL works without a live PostgreSQL connection.

---

## Consequences

### Positive

- **Fresh-DB migration works**: `alembic upgrade head` on an empty database creates all tables correctly.
- **Application layer is clean**: no storage-specific imports leak into domain/application code.
- **PostgreSQL-ready**: switching to PostgreSQL requires only a `DATABASE_URL` env var change.
- **Existing databases unaffected**: the idempotency check in `0001_baseline_schema` means existing
  production SQLite databases can run `alembic upgrade head` safely.
- **Test isolation**: `reset_engine()` + `rollback-per-test` pattern remains fully functional.

### Negative / Trade-offs

- The baseline migration is intentionally **not a full autogenerated diff** — it captures the historical
  schema state as of the Alembic introduction point. Future autogeneration must account for this.
- `Sqlite*Repository` class names are now misleading (they work on any dialect), but renaming them
  would be a separate refactoring with its own migration risk.

---

## Verification

- `uv run pytest` — **216 tests passed**, 0 failed, 0 errors.
- `uv run ruff check .` — **clean** (8 import-sort issues auto-fixed).
- `uv run mypy src` — **clean** (150 source files, 0 issues).
- `uv run alembic current` — **94579f682a90 (head)** — existing DB unaffected.
- Fresh-DB migration smoke test — all 5 migrations run successfully on empty SQLite DB.
