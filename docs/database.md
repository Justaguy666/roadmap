# Database Design — RoadmapAI

> **Version:** 1.0  
> **Last updated:** 2026-09-05  
> **Status:** Living document

---

## Table of Contents

1. [Strategy: SQLite dev / PostgreSQL prod](#1-strategy-sqlite-dev--postgresql-prod)
2. [Table Schemas](#2-table-schemas)
3. [Migration Strategy with Alembic](#3-migration-strategy-with-alembic)
4. [JSON Columns](#4-json-columns)
5. [SQLite WAL Mode & PRAGMA Settings](#5-sqlite-wal-mode--pragma-settings)
6. [Future PostgreSQL Migration Path](#6-future-postgresql-migration-path)

---

## 1. Strategy: SQLite dev / PostgreSQL prod

RoadmapAI uses a **two-database strategy** that optimises for developer ergonomics without sacrificing production reliability.

### 1.1 SQLite (development & local installs)

| Attribute | Value |
|---|---|
| Driver | `aiosqlite` (async) / `sqlite3` (sync fallback) |
| Default path | `~/.local/share/roadmapai/roadmap.db` (Linux/macOS) or `%APPDATA%\roadmapai\roadmap.db` (Windows) |
| WAL mode | **Enabled** (see §5) |
| Zero-config | Yes — created automatically on first run |

SQLite is the default and requires no installation. It covers 100% of the single-user CLI use case and is used in all local development and CI unit tests.

### 1.2 PostgreSQL (production / hosted)

| Attribute | Value |
|---|---|
| Driver | `asyncpg` (async) / `psycopg2` (sync) |
| Activation | Set `DATABASE_URL=postgresql+asyncpg://...` environment variable |
| Min version | PostgreSQL 14+ |
| Connection pool | SQLAlchemy `AsyncEngine` with `pool_size=5, max_overflow=10` |

PostgreSQL is used when `DATABASE_URL` starts with `postgresql://` or `postgresql+asyncpg://`. The application code is identical in both cases — only the engine creation differs.

### 1.3 URL-based switching

```python
# infrastructure/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = settings.database_url  # from environment

if DATABASE_URL.startswith("sqlite"):
    engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    _apply_sqlite_pragmas(engine)
else:
    engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10)
```

---

## 2. Table Schemas

All tables use `UUID` primary keys stored as `CHAR(36)` in SQLite and native `UUID` type in PostgreSQL. Timestamps are always UTC.

---

### 2.1 `user_profiles`

```sql
CREATE TABLE user_profiles (
    id           CHAR(36)     NOT NULL PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    email        VARCHAR(255),
    preferences  TEXT         NOT NULL,   -- JSON
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `CHAR(36)` | PK, NOT NULL | UUID v4 |
| `name` | `VARCHAR(255)` | NOT NULL | Display name |
| `email` | `VARCHAR(255)` | NULLABLE | Optional contact email |
| `preferences` | `TEXT` | NOT NULL | JSON — `LearningPreferences` VO |
| `created_at` | `DATETIME` | NOT NULL | UTC creation time |
| `updated_at` | `DATETIME` | NOT NULL | UTC last-modified time |

---

### 2.2 `user_skills`

Stores the user's current skill entries. Separate table (not JSON) to allow future querying/filtering.

```sql
CREATE TABLE user_skills (
    id           CHAR(36)     NOT NULL PRIMARY KEY,
    user_id      CHAR(36)     NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    skill_name   VARCHAR(255) NOT NULL,
    skill_level  VARCHAR(20)  NOT NULL,   -- NONE | BEGINNER | INTERMEDIATE | ADVANCED | EXPERT
    UNIQUE (user_id, skill_name)
);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `CHAR(36)` | PK | UUID v4 |
| `user_id` | `CHAR(36)` | FK → `user_profiles.id` | Owner |
| `skill_name` | `VARCHAR(255)` | NOT NULL | Canonical skill name |
| `skill_level` | `VARCHAR(20)` | NOT NULL | `SkillLevel` enum value |

---

### 2.3 `roadmaps`

```sql
CREATE TABLE roadmaps (
    id                     CHAR(36)      NOT NULL PRIMARY KEY,
    user_id                CHAR(36)      NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    goal                   TEXT          NOT NULL,
    status                 VARCHAR(20)   NOT NULL DEFAULT 'DRAFT',
    total_estimated_hours  REAL          NOT NULL DEFAULT 0.0,
    revision_count         INTEGER       NOT NULL DEFAULT 0,
    created_at             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_roadmaps_user_id ON roadmaps(user_id);
CREATE INDEX idx_roadmaps_status  ON roadmaps(status);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `CHAR(36)` | PK | UUID v4 |
| `user_id` | `CHAR(36)` | FK → `user_profiles.id` | Owner |
| `goal` | `TEXT` | NOT NULL | The user's stated learning goal |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT `'DRAFT'` | `DRAFT/ACTIVE/COMPLETED/ARCHIVED` |
| `total_estimated_hours` | `REAL` | NOT NULL | Derived sum of milestone hours |
| `revision_count` | `INTEGER` | NOT NULL | Number of agent revisions (MVP-2+) |
| `created_at` / `updated_at` | `DATETIME` | NOT NULL | UTC timestamps |

---

### 2.4 `skills`

```sql
CREATE TABLE skills (
    id               CHAR(36)     NOT NULL PRIMARY KEY,
    roadmap_id       CHAR(36)     NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    name             VARCHAR(255) NOT NULL,
    description      TEXT         NOT NULL DEFAULT '',
    category         VARCHAR(100) NOT NULL DEFAULT '',
    target_level     VARCHAR(20)  NOT NULL,
    estimated_hours  REAL         NOT NULL DEFAULT 1.0,
    prerequisites    TEXT         NOT NULL DEFAULT '[]',  -- JSON array of UUID strings
    tags             TEXT         NOT NULL DEFAULT '[]',  -- JSON array of strings
    UNIQUE (roadmap_id, name)
);

CREATE INDEX idx_skills_roadmap_id ON skills(roadmap_id);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `CHAR(36)` | PK | UUID v4 |
| `roadmap_id` | `CHAR(36)` | FK → `roadmaps.id` | Parent roadmap |
| `name` | `VARCHAR(255)` | NOT NULL, UNIQUE per roadmap | Canonical skill name |
| `description` | `TEXT` | NOT NULL | What knowing this skill means |
| `category` | `VARCHAR(100)` | NOT NULL | Broad grouping |
| `target_level` | `VARCHAR(20)` | NOT NULL | Required `SkillLevel` |
| `estimated_hours` | `REAL` | NOT NULL | Hours to reach `target_level` |
| `prerequisites` | `TEXT` | NOT NULL | **JSON** — list of skill `id` strings |
| `tags` | `TEXT` | NOT NULL | **JSON** — list of tag strings |

---

### 2.5 `milestones`

```sql
CREATE TABLE milestones (
    id               CHAR(36)     NOT NULL PRIMARY KEY,
    roadmap_id       CHAR(36)     NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    title            VARCHAR(255) NOT NULL,
    description      TEXT         NOT NULL DEFAULT '',
    skill_ids        TEXT         NOT NULL DEFAULT '[]',  -- JSON array of UUID strings
    priority         VARCHAR(20)  NOT NULL DEFAULT 'MEDIUM',
    estimated_hours  REAL         NOT NULL DEFAULT 1.0,
    status           VARCHAR(20)  NOT NULL DEFAULT 'NOT_STARTED',
    sequence_number  INTEGER      NOT NULL,
    completed_at     DATETIME,
    UNIQUE (roadmap_id, sequence_number)
);

CREATE INDEX idx_milestones_roadmap_id ON milestones(roadmap_id);
CREATE INDEX idx_milestones_status     ON milestones(status);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `CHAR(36)` | PK | UUID v4 |
| `roadmap_id` | `CHAR(36)` | FK → `roadmaps.id` | Parent roadmap |
| `title` | `VARCHAR(255)` | NOT NULL | Human-readable title |
| `description` | `TEXT` | NOT NULL | Milestone description |
| `skill_ids` | `TEXT` | NOT NULL | **JSON** — list of `skills.id` UUIDs |
| `priority` | `VARCHAR(20)` | NOT NULL | `CRITICAL/HIGH/MEDIUM/LOW` |
| `estimated_hours` | `REAL` | NOT NULL | Time estimate |
| `status` | `VARCHAR(20)` | NOT NULL | `NOT_STARTED/IN_PROGRESS/DONE/SKIPPED` |
| `sequence_number` | `INTEGER` | NOT NULL, UNIQUE per roadmap | 1-based ordering |
| `completed_at` | `DATETIME` | NULLABLE | Set when `status = DONE` |

---

### 2.6 `resources`

```sql
CREATE TABLE resources (
    id                  CHAR(36)     NOT NULL PRIMARY KEY,
    milestone_id        CHAR(36)     NOT NULL REFERENCES milestones(id) ON DELETE CASCADE,
    title               VARCHAR(255) NOT NULL,
    url                 TEXT         NOT NULL,
    resource_type       VARCHAR(20)  NOT NULL,
    is_free             BOOLEAN      NOT NULL DEFAULT TRUE,
    estimated_minutes   INTEGER
);

CREATE INDEX idx_resources_milestone_id ON resources(milestone_id);
```

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `CHAR(36)` | PK | UUID v4 |
| `milestone_id` | `CHAR(36)` | FK → `milestones.id` | Parent milestone |
| `title` | `VARCHAR(255)` | NOT NULL | Resource title |
| `url` | `TEXT` | NOT NULL | Source URL |
| `resource_type` | `VARCHAR(20)` | NOT NULL | `ARTICLE/VIDEO/COURSE/BOOK/PODCAST/TOOL` |
| `is_free` | `BOOLEAN` | NOT NULL | Freely available? |
| `estimated_minutes` | `INTEGER` | NULLABLE | Consumption time |

---

## 3. Migration Strategy with Alembic

RoadmapAI uses **Alembic** for database schema migrations. Migrations are generated automatically from SQLAlchemy model changes and stored under `infrastructure/db/migrations/`.

### 3.1 Directory layout

```
roadmap/
└── infrastructure/
    └── db/
        ├── models.py          # SQLAlchemy ORM models (source of truth)
        ├── session.py         # Engine / session factory
        └── migrations/
            ├── env.py         # Alembic env (imports models for autogenerate)
            ├── script.py.mako # Migration template
            └── versions/
                ├── 0001_initial_schema.py
                ├── 0002_add_revision_count.py
                └── ...
```

### 3.2 `render_as_batch=True` for SQLite compatibility

SQLite does not support `ALTER TABLE … ADD CONSTRAINT`, `DROP COLUMN`, or `RENAME COLUMN` in the way PostgreSQL does. Alembic's **batch mode** rewrites the affected table by:

1. Creating a new table with the desired schema.
2. Copying data across.
3. Dropping the old table.
4. Renaming the new table.

This is enabled globally in `env.py`:

```python
# migrations/env.py
with context.begin_transaction():
    context.run_migrations(render_as_batch=True)
```

### 3.3 Common commands

```bash
# Generate a migration from model changes
alembic revision --autogenerate -m "add_revision_count_to_roadmaps"

# Apply all pending migrations
alembic upgrade head

# Downgrade one step
alembic downgrade -1

# Show current revision
alembic current

# Show full history
alembic history --verbose
```

### 3.4 Running migrations at startup

In production, migrations are run automatically on application startup if `AUTO_MIGRATE=true` (default: `false` for safety in prod):

```python
# infrastructure/db/session.py
if settings.auto_migrate:
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
```

### 3.5 CI workflow

1. Spin up a fresh SQLite database (no env vars needed).
2. Run `alembic upgrade head`.
3. Run the full test suite.
4. Assert `alembic current` shows `head`.

---

## 4. JSON Columns

Several columns store structured data as JSON strings. This is a deliberate trade-off.

### 4.1 Columns using JSON storage

| Table | Column | Type | Reason |
|---|---|---|---|
| `user_profiles` | `preferences` | `LearningPreferences` object | Single-owner VO, never queried individually |
| `skills` | `prerequisites` | `list[UUID]` | Set of references; graph logic handled in Python |
| `skills` | `tags` | `list[str]` | Lightweight labels; no relational query needed |
| `milestones` | `skill_ids` | `list[UUID]` | Join list; milestone→skill is handled in Python |

### 4.2 Why JSON instead of junction tables?

- **Simplicity:** The data is always read and written as a unit with its parent row. There is no use case for querying `SELECT * FROM skill_prerequisites WHERE prerequisite_id = ?` independently.
- **Performance:** Avoiding extra joins for common read paths (load a roadmap → get its milestones → get their skills) reduces query count.
- **Correctness:** Graph logic (cycle detection, topological sort) runs in Python/NetworkX on the full in-memory graph. SQL-level relational joins add no correctness value.

### 4.3 Trade-offs and mitigations

| Risk | Mitigation |
|---|---|
| Can't query individual JSON array members in SQLite | Not needed; all filtering is Python-side |
| PostgreSQL JSON operators not available in SQLite | All JSON parsing uses Python `json.loads()` — no DB-side JSON functions |
| Schema evolution inside JSON columns is untracked by Alembic | JSON structure changes are managed via Pydantic model versioning + migration scripts when breaking |

---

## 5. SQLite WAL Mode & PRAGMA Settings

When the database URL is SQLite, the following PRAGMA settings are applied after every new connection:

```python
# infrastructure/db/session.py

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")       # (1)
    cursor.execute("PRAGMA synchronous=NORMAL")     # (2)
    cursor.execute("PRAGMA foreign_keys=ON")        # (3)
    cursor.execute("PRAGMA cache_size=-64000")      # (4)
    cursor.execute("PRAGMA temp_store=MEMORY")      # (5)
    cursor.execute("PRAGMA mmap_size=268435456")    # (6) 256 MB
    cursor.close()
```

### Setting explanations

| # | PRAGMA | Value | Reason |
|---|---|---|---|
| 1 | `journal_mode` | `WAL` | Write-Ahead Logging allows concurrent readers during writes; dramatically improves read performance |
| 2 | `synchronous` | `NORMAL` | Safe with WAL; avoids full `fsync` on every write while maintaining crash safety at the WAL level |
| 3 | `foreign_keys` | `ON` | SQLite does not enforce FK constraints by default; this enables them |
| 4 | `cache_size` | `-64000` | 64 MB page cache (negative = kilobytes); reduces disk I/O for repeat reads |
| 5 | `temp_store` | `MEMORY` | Temporary tables and indices live in memory rather than disk |
| 6 | `mmap_size` | `268435456` | 256 MB memory-mapped I/O window; improves large sequential reads |

### WAL checkpoint

WAL files are check-pointed automatically by SQLite when they reach 1000 pages. For long-running CLI sessions, an explicit checkpoint can be triggered:

```python
session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
```

---

## 6. Future PostgreSQL Migration Path

When the user outgrows SQLite (e.g. hosted web UI, multi-user mode), the path to PostgreSQL is straightforward.

### 6.1 Schema changes

| SQLite type | PostgreSQL equivalent | Notes |
|---|---|---|
| `CHAR(36)` | `UUID` | Native UUID type; change column type in migration |
| `TEXT` (JSON) | `JSONB` | Superior — adds GIN-indexable JSON operators |
| `REAL` | `DOUBLE PRECISION` | Direct equivalent |
| `BOOLEAN` | `BOOLEAN` | Direct equivalent (SQLite stores as integer) |
| `DATETIME` | `TIMESTAMPTZ` | Always UTC; add timezone awareness |

### 6.2 Migration procedure

1. **Add a new Alembic migration** that changes column types for PostgreSQL only (using `op.get_context().dialect.name` guard).
2. **Export SQLite data** via `sqlite3 roadmap.db .dump > dump.sql` and transform with a simple Python script.
3. **Load into PostgreSQL** using `psql -f transformed_dump.sql`.
4. **Set `DATABASE_URL`** to the PostgreSQL connection string.
5. **Run `alembic upgrade head`** to apply any remaining schema deltas.

### 6.3 Benefits gained at PostgreSQL

- Native `JSONB` operators for querying inside JSON columns (if needed).
- Row-level locking for concurrent write safety.
- Full-text search on `skills.name` and `skills.description` using `tsvector`.
- `pg_stat_statements` for query performance monitoring.
- Proper UUID primary key type with index efficiency.

### 6.4 Connection string examples

```bash
# SQLite (default, local)
DATABASE_URL=sqlite+aiosqlite:///~/.local/share/roadmapai/roadmap.db

# PostgreSQL (production)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/roadmapai

# PostgreSQL (Render.com / Railway typical format)
DATABASE_URL=postgresql+asyncpg://roadmapai_user:s3cr3t@dpg-xyz.oregon-postgres.render.com/roadmapai
```
