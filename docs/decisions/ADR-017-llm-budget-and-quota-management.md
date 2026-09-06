# ADR-017: LLM Budget & Quota Management

## Status
Accepted

## Context
In RoadmapAI, user workflows (such as market/resource research, candidate roadmap generation, and evaluator-agent revision loops) make multiple structured completions against upstream LLM providers (e.g., Google Gemini, OpenAI). When running on free-tier or rate-limited upstream tiers, request storms can rapidly exhaust daily quotas (e.g., 429 RESOURCE_EXHAUSTED).
Previously, when the quota was exhausted during research, subsequent commands such as `roadmap generate` failed abruptly with unhandled upstream 429 errors. Furthermore, there was no centralized mechanism to budget, reserve, track, or report LLM request usage across different workflows.

## Decision
We introduced a provider-agnostic **LLM Budget & Quota Management** layer that operates above concrete LLM providers:

1. **Failure Classification & Categorization**:
   - Upstream LLM errors are mapped to `FailureCategory` (e.g., `APPLICATION_BUDGET_EXCEEDED`, `PROVIDER_DAILY_QUOTA_EXCEEDED`, `PROVIDER_RATE_LIMITED`, `AUTHENTICATION_ERROR`, `TRANSIENT_PROVIDER_ERROR`).
   - 429 daily quota exhaustion triggers a persistent provider cooldown (default 3600 seconds), preventing repeated requests to an exhausted provider.

2. **Application Budgeting & Two-Phase Reservations**:
   - Workflows (`research`, `generation`, `evaluation`) have dedicated daily request caps (configurable via environment variables: `DAILY_LLM_BUDGET`, `RESEARCH_LLM_BUDGET`, `GENERATION_LLM_BUDGET`, `EVALUATION_LLM_BUDGET`).
   - Workflows must **reserve** budget capacity before attempting an LLM call. Active uncommitted reservations are counted against current limits.
   - If capacity is exhausted or the upstream provider is in cooldown, `ApplicationBudgetExceededError` or `ProviderQuotaUnavailableError` is raised immediately without invoking the LLM.
   - Upon completion or failure, reservations are **committed** (recording actual request count and failure category) or **released**.

3. **Persistence & Observability**:
   - Usage records (`llm_usage_records`) and provider health states (`llm_provider_states`) are persisted to SQLite via SQLAlchemy and Alembic (`881408fd6535_create_llm_budget_and_quota_tables.py`).
   - A dedicated CLI command `roadmap quota [--json]` allows users and automation to inspect budget allocations, remaining requests, provider cooldowns, and recent request outcomes.

## Consequences
### Positive
- Prevents upstream request storms and quota exhaustion.
- Fails fast and deterministically with clear, actionable error messages instead of raw API traces.
- Preserves full support for mock and alternative LLM providers in local test runs.
- Maintains Clean Architecture principles: Domain and application layers remain decoupled from concrete provider SDKs.

### Negative / Trade-offs
- Operations require reservation commits and SQLite writes, introducing minor database I/O for tracking.
