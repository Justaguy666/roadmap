# ADR-005 — SQLite for Development, PostgreSQL for Production

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-05 |
| **Deciders** | Engineering team |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Context

RoadmapAI requires persistent storage for user profiles, roadmaps, milestones, skills, and resources. We need to choose a persistence strategy that satisfies the following constraints:

1. **Local CLI install** must work with zero external services. A new user should run `pip install roadmapai` and get a fully working application — no PostgreSQL installation required.
2. **Production/hosted mode** (future web interface or multi-user deployment) needs a robust, scalable, multi-connection-safe database.
3. **Developer experience** must be frictionless. Running tests and developing new features should not require a running database daemon.
4. **Schema evolution** must be supported in both environments through a common migration tool.
5. **Application code** must be identical regardless of the underlying database engine — no SQLite-specific or PostgreSQL-specific logic in the application layer.

### Options considered

| Option | Notes |
|---|---|
| **SQLite only** | Zero-config; not suitable for multi-user/concurrent write production |
| **PostgreSQL only** | Requires Docker or a PostgreSQL install for all local development |
| **SQLite dev + PostgreSQL prod** | Best of both; supported by SQLAlchemy + Alembic |
| **DuckDB** | OLAP-oriented; excellent for analytics; less mature ecosystem for web-app-style workloads |
| **TinyDB / shelve** | No SQL; no migration tooling; not suitable for relational data |

---

## Decision

**SQLite is the default database** for local development and single-user CLI installs. **PostgreSQL is used in production** (and can be used in CI for integration testing). The active database is determined entirely by the `DATABASE_URL` environment variable.

### Switching logic

```python
# infrastructure/db/session.py

DATABASE_URL = settings.database_url
# Default: "sqlite+aiosqlite:///{user_data_dir}/roadmap.db"

if DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    _apply_sqlite_pragmas(engine)  # WAL mode, FK enforcement, cache tuning
else:
    engine = create_async_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
```

No application-layer or domain-layer code contains any conditional logic for the database type. The switch is **entirely** in the infrastructure layer.

### Alembic with `render_as_batch=True`

SQLite has significant DDL limitations compared to PostgreSQL:

- Cannot `ADD COLUMN ... NOT NULL` without a default.
- Cannot `DROP COLUMN`.
- Cannot `RENAME COLUMN` (pre SQLite 3.25).
- Cannot add or drop constraints (foreign keys, unique constraints) on existing tables.

Alembic's **batch migration mode** works around all these limitations by recreating the affected table:

```python
# migrations/env.py

def run_migrations_online() -> None:
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,       # ← Enables SQLite-safe migrations
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
```

`render_as_batch=True` is safe to leave enabled for PostgreSQL migrations too — when Alembic detects a PostgreSQL connection, it uses native DDL instead of the batch copy approach.

### Migration naming convention

Migrations use a sequential integer prefix for readability:

```
migrations/versions/
    0001_initial_schema.py
    0002_add_revision_count_to_roadmaps.py
    0003_add_resources_table.py
```

The Alembic revision ID (hex string) is preserved internally; the integer prefix is cosmetic for developer navigation.

---

## Consequences

### Positive

- **Zero-config onboarding** — `pip install roadmapai` and the SQLite database is created automatically on first use at a sensible platform-appropriate path.
- **No Docker required for development** — developers and CI environments do not need a running PostgreSQL daemon for unit or integration tests.
- **Production-grade persistence** — the same schema runs on PostgreSQL for hosted, multi-user deployments with full concurrent write safety.
- **Single migration codebase** — Alembic manages both environments. No separate schema files, no manual SQL, no drift between environments.
- **`render_as_batch`** makes SQLite a first-class migration citizen — schema changes (column additions, renames, constraint changes) work reliably in both databases.
- **Environment-variable driven** — switching from SQLite to PostgreSQL in CI requires only setting `DATABASE_URL`. No code changes.

### Negative

- **SQLite limitations in production** — SQLite does not support concurrent writers. If RoadmapAI ever becomes a multi-user web service, SQLite is not viable. This is a known and accepted trade-off for the current CLI use case.
- **Type differences** — SQLite stores `BOOLEAN` as integer and `UUID` as text. The ORM layer (SQLAlchemy) handles this transparently, but it creates minor complexity when inspecting the database directly with `sqlite3`.
- **`render_as_batch` table rewrites** — on large tables, batch migrations copy all data to a new table, which can be slow. Not a concern for the current data volumes (personal CLI tool).
- **Two database engines to test** — ideally CI runs tests against both SQLite (fast, default) and PostgreSQL (production fidelity). Currently only SQLite is used in CI. PostgreSQL compatibility is validated by type annotations, SQLAlchemy compatibility, and periodic manual testing.
- **JSON column type differences** — SQLite stores JSON as `TEXT`; PostgreSQL supports `JSONB` (with GIN indexing and JSON operators). The application uses Python-side `json.loads()` for all JSON parsing, so the runtime behaviour is identical — but the PostgreSQL performance benefits of `JSONB` are not exploited until a dedicated migration is run.

### Migration to PostgreSQL (future)

See [database.md §6](../database.md#6-future-postgresql-migration-path) for the full migration procedure. The key steps are: run a new Alembic migration to change column types (`CHAR(36)` → `UUID`, `TEXT` → `JSONB`, `DATETIME` → `TIMESTAMPTZ`), export/transform the SQLite data, and load into PostgreSQL.
