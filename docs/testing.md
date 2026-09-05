# Testing Strategy

RoadmapAI employs a multi-tiered testing strategy ensuring fast local execution, full deterministic reproducibility, and zero network dependencies during continuous integration.

## Test Suites

### 1. Unit Tests (	ests/unit/)
Tests pure business logic, domain entities, value objects, domain services, agent schemas, and use case orchestration.

- 	est_domain_entities.py: Invariant enforcement, immutability, and state transitions across domain models.
- 	est_roadmap_validator.py: Structural DAG validation, prerequisite ordering, and duration assertions.
- 	est_priority_calculator.py: Weighted skill prioritization and sorting logic.
- 	est_progress_tracker.py: Phase progress calculations and completion logic.
- 	est_agent_schemas.py: Pydantic schema validation for goal analysis and roadmap generation.
- 	est_openai_provider.py: Exception mapping and contract adherence for OpenAIProvider.
- 	est_analyze_goal_use_case.py: Execution of AnalyzeGoalUseCase with mocked/fake providers.
- 	est_generate_roadmap_use_case.py: Generation pipeline testing including bounded retry on validation failure.

### 2. Integration Tests (	ests/integration/)
Validates cross-layer behavior with real SQLite database persistence and full repository operations.

- 	est_db_repositories.py: Verifies SQLite storage operations for profiles, roadmaps, skills, milestones, and resources.
- 	est_roadmap_pipeline.py: End-to-end integration test verifying profile creation -> LLM goal analysis -> deterministic gap analysis -> LLM roadmap generation -> validation -> SQLite persistence -> retrieval.

---

## Testing with Fake LLM Provider

Tests never call external LLM APIs (OpenAI) directly. Instead, FakeLLMProvider (src/roadmap/infrastructure/llm/fake_provider.py) provides deterministic, type-safe responses:

`python
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.agents.schemas.goal_analysis import GoalAnalysisResult

fake_provider = FakeLLMProvider()
result = fake_provider.generate(messages=[], response_model=GoalAnalysisResult)
assert result.primary_career == Software Engineer
`

To configure custom failure scenarios or validation triggers, pass a list of responses or callables:

`python
fake_provider = FakeLLMProvider(responses=[invalid_draft, corrected_draft])
`

---

## Running Tests

`ash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=roadmap --cov-report=term-missing

# Run only unit tests
uv run pytest tests/unit

# Run only integration tests
uv run pytest tests/integration
`

## Linting & Type Checking

`ash
# Lint with ruff
uv run ruff check .

# Type check core source
uv run mypy src
`
