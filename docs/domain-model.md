# Domain Model — RoadmapAI

> **Version:** 1.0  
> **Last updated:** 2026-09-05  
> **Status:** Living document

---

## Table of Contents

1. [Overview](#1-overview)
2. [Entities](#2-entities)
3. [Value Objects](#3-value-objects)
4. [Domain Services](#4-domain-services)
5. [Entity Relationship Diagram](#5-entity-relationship-diagram)
6. [Invariants & Business Rules](#6-invariants--business-rules)

---

## 1. Overview

The domain model is the heart of RoadmapAI. It captures the *language of the business* — skills, learning gaps, roadmaps, milestones, and plans — in plain Python objects that contain no infrastructure concerns. Every object in this layer is fully testable without a database or network connection.

The model follows **Domain-Driven Design** (DDD) conventions:

- **Aggregates** enforce consistency boundaries.
- **Value Objects** are immutable and equality is determined by their fields, not their identity.
- **Domain Services** handle logic that doesn't naturally belong to a single entity.
- **Repository Ports** define how aggregates are persisted without coupling the domain to SQLAlchemy or any other ORM.

---

## 2. Entities

### 2.1 `UserProfile` (Aggregate Root)

Represents the learner using the system.

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | Globally unique identifier |
| `name` | `str` | Display name |
| `email` | `str \| None` | Optional contact email |
| `current_skills` | `list[SkillEntry]` | Skills the user already has, with level |
| `preferences` | `LearningPreferences` | Hours/week, preferred formats, etc. |
| `created_at` | `datetime` | Profile creation timestamp |
| `updated_at` | `datetime` | Last modification timestamp |

**Invariants:**
- `name` must be non-empty.
- `current_skills` must not contain duplicate skill names.

---

### 2.2 `Roadmap` (Aggregate Root)

The top-level planning artifact. A user may have multiple roadmaps (e.g. one per goal).

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | Globally unique identifier |
| `user_id` | `UUID` | FK to `UserProfile` |
| `goal` | `str` | The target outcome (e.g. "MLOps engineer") |
| `status` | `RoadmapStatus` | `DRAFT \| ACTIVE \| COMPLETED \| ARCHIVED` |
| `skill_graph` | `SkillGraph` | Directed acyclic graph of skills |
| `milestones` | `list[Milestone]` | Ordered list of milestones |
| `total_estimated_hours` | `float` | Sum of milestone estimates |
| `created_at` | `datetime` | — |
| `updated_at` | `datetime` | — |

**Invariants:**
- A `Roadmap` in `COMPLETED` status cannot transition back to `DRAFT`.
- `milestones` must preserve topological order relative to the `skill_graph`.
- `total_estimated_hours` is always recomputed from milestones — never set directly.

**Lifecycle:**
```
DRAFT ──► ACTIVE ──► COMPLETED
  │                      │
  └───────► ARCHIVED ◄───┘
```

---

### 2.3 `Milestone`

A discrete, time-boxed chunk of the learning plan. Each milestone covers one or more related skills.

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | — |
| `roadmap_id` | `UUID` | Parent roadmap |
| `title` | `str` | Human-readable title |
| `description` | `str` | What the learner will accomplish |
| `skills` | `list[UUID]` | Skill IDs covered by this milestone |
| `priority` | `Priority` | `CRITICAL \| HIGH \| MEDIUM \| LOW` |
| `estimated_hours` | `float` | Time estimate |
| `status` | `MilestoneStatus` | `NOT_STARTED \| IN_PROGRESS \| DONE \| SKIPPED` |
| `resources` | `list[Resource]` | Curated learning resources |
| `sequence_number` | `int` | 1-based position within the roadmap |
| `completed_at` | `datetime \| None` | Set when status → DONE |

**Invariants:**
- `estimated_hours` must be > 0.
- `sequence_number` must be unique within a roadmap.
- A milestone cannot be marked `DONE` unless all predecessor milestones (per the skill graph) are `DONE` or `SKIPPED`.

---

### 2.4 `Skill`

A single learnable capability — a node in the skill graph.

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | — |
| `name` | `str` | Canonical skill name (e.g. "Docker Networking") |
| `description` | `str` | What knowing this skill means |
| `category` | `str` | Broad grouping (e.g. "Infrastructure", "ML Ops") |
| `target_level` | `SkillLevel` | The level needed to satisfy the goal |
| `estimated_hours` | `float` | Raw learning hours for this skill |
| `prerequisites` | `list[UUID]` | Skill IDs that must be learned first |
| `tags` | `list[str]` | Free-form tags for search/filter |

**Invariants:**
- `name` must be unique within a skill graph.
- `prerequisites` must not create cycles (enforced by `SkillGraphService`).

---

### 2.5 `Resource`

A curated learning resource associated with a milestone.

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | — |
| `title` | `str` | Resource title |
| `url` | `str` | Source URL |
| `resource_type` | `ResourceType` | `ARTICLE \| VIDEO \| COURSE \| BOOK \| PODCAST \| TOOL` |
| `is_free` | `bool` | Whether the resource is freely available |
| `estimated_minutes` | `int \| None` | Approximate consumption time |

---

## 3. Value Objects

Value objects are **immutable**. Two value objects with the same field values are considered equal. They are never referenced by ID.

### 3.1 `SkillLevel`

Represents a learner's proficiency with a skill.

```
NONE < BEGINNER < INTERMEDIATE < ADVANCED < EXPERT
  0       1            2             3         4
```

| Member | Numeric value | Meaning |
|---|---|---|
| `NONE` | 0 | No knowledge |
| `BEGINNER` | 1 | Conceptual awareness; has tried basics |
| `INTERMEDIATE` | 2 | Can use independently on real projects |
| `ADVANCED` | 3 | Deep knowledge; can debug edge cases |
| `EXPERT` | 4 | Can teach; contributes to tooling |

**Ordering semantics:** `SkillLevel` supports `<`, `<=`, `>`, `>=`. A gap exists when `current_level < target_level`.

---

### 3.2 `Priority`

Ordered priority for milestones.

```
CRITICAL > HIGH > MEDIUM > LOW
    4        3      2       1
```

Used by the planner to schedule `CRITICAL` milestones first. When two milestones share a topological position, higher priority is scheduled earlier.

---

### 3.3 `Duration`

An immutable representation of a time span used for estimates.

```python
@dataclass(frozen=True)
class Duration:
    hours: float

    def to_weeks(self, hours_per_week: float) -> float: ...
    def __add__(self, other: "Duration") -> "Duration": ...
```

- Always stored and compared in **hours**.
- Converted to weeks/days only for display purposes.

---

### 3.4 `SkillEntry`

A user's current possession of a skill at a specific level.

```python
@dataclass(frozen=True)
class SkillEntry:
    skill_name: str
    level: SkillLevel
```

Used within `UserProfile.current_skills`. The `skill_name` is a canonical string that maps to `Skill.name` during gap analysis.

---

### 3.5 `LearningPreferences`

User preferences that influence planning.

```python
@dataclass(frozen=True)
class LearningPreferences:
    hours_per_week: float          # default: 10.0
    preferred_formats: list[ResourceType]
    start_date: date
    target_end_date: date | None   # None = no deadline
```

---

### 3.6 `GapItem`

Represents a single identified skill gap.

```python
@dataclass(frozen=True)
class GapItem:
    skill_name: str
    current_level: SkillLevel
    target_level: SkillLevel

    @property
    def gap_size(self) -> int:
        return self.target_level.value - self.current_level.value
```

---

### 3.7 `SearchResult`

Returned by the `SearchProvider` port.

```python
@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    score: float   # provider-assigned relevance score
```

---

## 4. Domain Services

Domain services hold logic that is too complex or spans multiple entities to live on a single entity.

### 4.1 `GapAnalysisService`

**Location:** `domain/services/gap_analysis.py`

**Responsibility:** Compares a user's `current_skills` against the skills required to reach the stated goal, producing a list of `GapItem` objects.

```
inputs:  UserProfile, list[Skill]  (required skills for the goal)
outputs: list[GapItem]
```

**Key logic:**
- Skills the user already knows at or above `target_level` are excluded.
- Skills the user partially knows (e.g. `BEGINNER` when `ADVANCED` is needed) are included with a partial gap.
- Skills the user has no knowledge of are included with full gap.

---

### 4.2 `SkillGraphService`

**Location:** `domain/services/skill_graph.py`

**Responsibility:** Constructs, validates, and queries the directed skill dependency graph.

```
inputs:  list[Skill]   (with prerequisite edges)
outputs: SkillGraph (validated DAG), or raises CycleDetectedError
```

**Key operations:**

| Operation | Description |
|---|---|
| `build_graph(skills)` | Constructs a NetworkX `DiGraph` from skill prerequisite lists |
| `validate_dag(graph)` | Raises `CycleDetectedError` if the graph contains a cycle |
| `topological_order(graph)` | Returns skills in a valid learning sequence |
| `get_prerequisites(skill_id)` | Returns all transitive prerequisites for a skill |
| `get_dependents(skill_id)` | Returns all skills that depend on this skill |

**Trust model:** This service is the authoritative validator. LLM-proposed edges are passed through `validate_dag` before any plan is built. The LLM is **never** trusted to provide a cycle-free graph without validation.

---

### 4.3 `PlanningService`

**Location:** `domain/services/planning.py`

**Responsibility:** Takes a validated `SkillGraph` and a `UserProfile` and produces an ordered list of `Milestone` objects.

```
inputs:  SkillGraph, list[GapItem], LearningPreferences
outputs: list[Milestone]
```

**Key logic:**
- Skills are grouped into milestones by thematic proximity and shared prerequisites.
- Within a valid topological order, milestones are ordered by `Priority` (descending).
- Each milestone's `estimated_hours` is set from the sum of its constituent skills' estimates.
- Milestones that exceed `hours_per_week × 2` are split to keep chunks manageable.

---

## 5. Entity Relationship Diagram

```
┌──────────────────┐          ┌─────────────────────────────────────┐
│   UserProfile    │          │              Roadmap                 │
│──────────────────│  1    *  │─────────────────────────────────────│
│ id (PK)          │◄─────────│ id (PK)                             │
│ name             │          │ user_id (FK → UserProfile)          │
│ email            │          │ goal                                 │
│ current_skills[] │          │ status                              │
│ preferences      │          │ total_estimated_hours               │
└──────────────────┘          └──────────────┬──────────────────────┘
                                             │ 1
                                             │ contains
                                             │ *
                               ┌─────────────▼──────────────────────┐
                               │           Milestone                 │
                               │────────────────────────────────────│
                               │ id (PK)                             │
                               │ roadmap_id (FK → Roadmap)          │
                               │ title                               │
                               │ description                         │
                               │ skills[] (FK → Skill)              │
                               │ priority                            │
                               │ estimated_hours                     │
                               │ status                              │
                               │ sequence_number                     │
                               └──────────────┬──────────────────────┘
                                              │ *
                                              │ contains
                                              │ *
                               ┌──────────────▼──────────────────────┐
                               │            Resource                  │
                               │─────────────────────────────────────│
                               │ id (PK)                              │
                               │ milestone_id (FK → Milestone)        │
                               │ title                                │
                               │ url                                  │
                               │ resource_type                        │
                               │ is_free                              │
                               │ estimated_minutes                    │
                               └──────────────────────────────────────┘

                                    SkillGraph (in-memory)
                               ┌──────────────────────────────────────┐
                               │  Skill ───► Skill ───► Skill         │
                               │  (nodes)   (directed prerequisite    │
                               │             edges = DAG)             │
                               └──────────────────────────────────────┘
```

---

## 6. Invariants & Business Rules

### 6.1 Graph Integrity

- The skill dependency graph **must** be a Directed Acyclic Graph (DAG) at all times.
- A `CycleDetectedError` is raised if any proposed edge would create a cycle.
- `topological_sort()` is always available and deterministic (ties broken alphabetically).

### 6.2 Roadmap Consistency

- A `Roadmap` must have at least one `Milestone` before it can transition from `DRAFT` to `ACTIVE`.
- `total_estimated_hours` is a derived property — it is never directly set; it is always recalculated as `sum(m.estimated_hours for m in milestones)`.
- Milestones within a roadmap must be ordered consistently with the topological order of the skill graph.

### 6.3 Milestone Completion Order

- A milestone may only be marked `DONE` if all milestones it depends on (via skill prerequisites) are `DONE` or `SKIPPED`.
- Setting a milestone to `SKIPPED` propagates a warning if dependent milestones exist, but does not block them.

### 6.4 Skill Uniqueness

- Within a single roadmap's skill graph, no two `Skill` nodes may have the same `name` (case-insensitive).
- A `DuplicateSkillError` is raised if a duplicate is added.

### 6.5 Gap Analysis

- A skill with `current_level >= target_level` produces **no** `GapItem` — it is considered satisfied.
- Gap analysis results are **read-only** value objects; they do not mutate the `UserProfile`.

### 6.6 Estimated Hours

- `Skill.estimated_hours` must be a positive float (`> 0`).
- `Milestone.estimated_hours` must be a positive float (`> 0`).
- Hours are stored as raw float values in hours. Conversion to days/weeks/months is a display concern handled in the CLI layer.

### 6.7 Revision Limits (Multi-Agent, MVP-2+)

- The agent revision loop **must not** exceed `MAX_REVISIONS = 3` iterations.
- After 3 revisions without acceptance, the highest-scored draft is used and a user-visible warning is emitted.
- This invariant is enforced by the `OrchestratorAgent`, not by domain objects.
