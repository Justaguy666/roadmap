# RoadmapAI

**AI-powered adaptive learning and career roadmap agent.**

RoadmapAI researches your target career, analyzes your current skills and skill gaps, searches the job market and learning resources, constructs an evidence-based roadmap, explains every decision, and continuously adapts as you progress.

---

## Quick Start

```bash
# Install (requires Python 3.11+)
pip install uv
uv sync

# Create your profile
roadmap init

# View your profile
roadmap profile show

# Generate your roadmap (MVP-2, coming next)
roadmap generate

# View your roadmap
roadmap show

# Track progress
roadmap progress
```

---

## Commands

| Command | Description | MVP |
|---|---|---|
| `roadmap init` | Create user profile interactively | 1 ✓ |
| `roadmap profile show` | Display current profile | 1 ✓ |
| `roadmap profile edit` | Edit profile fields | 1 ✓ |
| `roadmap profile reset` | Delete profile | 1 ✓ |
| `roadmap analyze` | Analyze goal, competencies, and skill gaps | 2 ✓ |
| `roadmap generate` | AI roadmap generation with validation & persistence | 2 ✓ |
| `roadmap show` | Show roadmap overview | 1/2 ✓ |
| `roadmap show --phase N` | Show phase N details | 1/2 ✓ |
| `roadmap progress` | Progress dashboard | 1 ✓ |
| `roadmap research` | Market + resource research | 3 |
| `roadmap research --refresh` | Force re-research | 3 |
| `roadmap complete <skill>` | Mark skill complete | 5 |
| `roadmap update` | Adaptive replanning | 5 |
| `roadmap why <skill>` | Explain a recommendation | 5 |
| `roadmap sources` | List research sources | 3 |
| `roadmap export --format json` | Export roadmap | 6 |
| `roadmap export --format markdown` | Export roadmap | 6 |

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Key settings:

```env
ROADMAP_DATA_DIR=~/.roadmap        # where data is stored
OPENAI_API_KEY=sk-...              # for MVP-2+ LLM features
EXA_API_KEY=...                    # for MVP-3+ research features
```

---

## Architecture

```
roadmap/
├── src/roadmap/
│   ├── cli/            # Typer + Rich CLI (presentation layer)
│   ├── domain/         # Pure business logic — NO external deps
│   │   ├── entities/   # UserProfile, Skill, Roadmap, ...
│   │   ├── value_objects/  # SkillLevel, Priority, ...
│   │   └── services/   # SkillGapAnalyzer, PriorityCalculator, ...
│   ├── application/    # Use cases + port interfaces
│   ├── agents/         # Multi-agent orchestration (MVP-2+)
│   ├── infrastructure/ # LLM, Search, Cache adapters
│   ├── storage/        # SQLAlchemy models + repositories
│   ├── research/       # Research pipeline (MVP-3+)
│   └── config/         # Pydantic Settings
```

**Dependency rule:** `cli → application → domain`  
Domain never imports from CLI, infrastructure, or database.

See [`docs/architecture.md`](docs/architecture.md) for full details.

---

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=src/roadmap --cov-report=term-missing

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/ tests/

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

---

## MVP Status

- [x] **MVP-1** — Foundation: domain model, SQLite, CLI, profile management, unit tests
- [ ] **MVP-2** — LLM integration: OpenAI, structured outputs, goal + skill analysis
- [ ] **MVP-3** — Web research: Exa, evidence system, source quality
- [ ] **MVP-4** — Multi-agent: orchestrator, evaluator/revision loop, skill graph
- [ ] **MVP-5** — Adaptive: progress tracking, replanning, explainability
- [ ] **MVP-6** — Export, vector search, observability

---

## License

MIT
