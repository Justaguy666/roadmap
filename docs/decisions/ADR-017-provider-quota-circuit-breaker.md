# ADR-017: Provider Daily-Quota Circuit Breaker, Fail-Fast Persistence, and Re-Probe Semantics

## Status
Accepted

## Context
In RoadmapAI, multiple workflows (`research`, `generation`, and `evaluation`) interact with external LLM providers such as Google Gemini and OpenAI. When invoking Gemini free-tier, Google AI Studio enforces strict daily quotas (e.g. `GenerateRequestsPerDayPerModel-FreeTier`, 20 requests/day).

When this quota is exhausted, Gemini returns `429 RESOURCE_EXHAUSTED` with error details indicating `generate_content_free_tier_requests` has reached its ceiling. The error body also includes transient advisory attributes such as `retryDelay` (e.g., 23s or 49s). However, this retry delay is an advisory backoff interval for transient concurrency/burst limits; it does **not** indicate when the provider's daily quota window resets (which resets midnight PST / 08:00 UTC).

Previously:
1. Short-term advisory retry delays were conflated with daily quota reset times.
2. If an application treated transient cooldowns as daily resets, subsequent workflow executions would immediately re-attempt network calls to the provider, incurring pointless latency, quota waste, and unhandled 429 exceptions.
3. Multiple CLI processes running sequentially (e.g. `roadmap research`, then `roadmap generate`) need a shared persistent understanding of provider quota exhaustion to fail fast *before* making any network requests.

## Decision

### 1. Conceptual Distinction Between Quota Window and Circuit Breaker
We explicitly distinguish three orthogonal concepts:
- **Application Budget (`LLMBudgetManager`)**: Local proactive limits preventing unexpected local overuse across workflows.
- **Provider Quota Window (`quota_exhausted`)**: The upstream provider's server-side daily quota constraint.
- **Circuit Breaker (`blocked_until`)**: A local defensive mechanism that stops all outgoing network requests to an exhausted provider for a configurable cooldown window (`llm_cooldown_seconds`, default 3600s).

### 2. Controlled Re-Probe Semantics
When a provider encounters `PROVIDER_DAILY_QUOTA_EXCEEDED`:
- The provider state is marked with `quota_exhausted = True` and `blocked_until = now + timedelta(seconds=cooldown_seconds)`.
- During the `blocked_until` window: Any attempt to reserve LLM capacity for that provider/model immediately raises `ProviderQuotaUnavailableError` with zero network calls made.
- When `blocked_until` expires: The system enters a **half-open / re-probe** state. Exactly one request is permitted to probe upstream provider health.
  - If the re-probe **succeeds**: The circuit breaker closes, `quota_exhausted` is reset to `False`, and `blocked_until` is cleared.
  - If the re-probe **fails** with daily quota exhaustion again: The circuit breaker re-arms, setting a new `blocked_until` interval.

### 3. Persistent Shared State Across Workflows
Provider states are persisted to SQLite in the `llm_provider_states` table, keyed by `(provider, model)`.
All workflows (`research`, `generation`, `evaluation`) consult the repository before issuing network requests. Blocked requests are intercepted at the budget reservation phase, ensuring zero provider API calls and zero false usage increments in `llm_usage_records`.

### 4. Transparent CLI Reporting
The `roadmap quota` command reports:
- Application-level budgets (global and per-workflow).
- Upstream provider health, clearly distinguishing `ACTIVE` circuit-breaker states from confirmed upstream reset times.
- Explicit footnote clarifying that re-probe times reflect local circuit-breaker cooldowns rather than upstream provider reset confirmations.

## Consequences
- **Positive**: Zero network calls on subsequent commands when daily quota is exhausted. Instant fail-fast feedback in CLI.
- **Positive**: Resilient against upstream transient retry suggestions corrupting daily quota tracking.
- **Positive**: Automatic self-healing via re-probe once the cooldown expires or next day begins.
- **Negative**: If an upstream quota resets before the circuit breaker expires, the user may wait up to the cooldown duration unless manually cleared.
