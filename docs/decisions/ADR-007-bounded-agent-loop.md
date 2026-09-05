# ADR-007 — Bounded Revision Loop for Multi-Agent Evaluation

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-05 |
| **Deciders** | Engineering team |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Context

In MVP-2+, roadmap generation is enhanced by a **multi-agent evaluation loop**:

1. The **Curriculum Agent** produces a draft roadmap.
2. The **Critic Agent** evaluates the draft against a quality rubric and emits feedback or an acceptance signal.
3. If the Critic rejects the draft, the Curriculum Agent revises and resubmits.
4. Steps 2–3 repeat until the Critic accepts or a termination condition is met.

### The infinite loop problem

Without an explicit termination condition, this loop can recurse indefinitely under several failure modes:

| Failure mode | Description |
|---|---|
| **Critic too strict** | The Critic's rubric is impossible to fully satisfy; it always rejects |
| **Curriculum can't improve** | The Curriculum Agent reaches its capability ceiling; further revisions are circular |
| **Adversarial feedback cycle** | Critic feedback causes regression in previously satisfied criteria |
| **LLM non-determinism** | With temperature > 0, both agents behave differently each call; they may oscillate |
| **Expensive token consumption** | Each revision cycle burns API tokens. Without a cap, a single roadmap generation could cost dollars |

### Options considered

1. **No limit (trust the loop to converge)** — rejected; all four failure modes above have been observed in agent system testing.
2. **Time-based limit** — e.g. "stop after 60 seconds". Unpredictable; depends on API latency.
3. **Convergence detection** — stop if Critic score stops improving between revisions. Adds complexity; score may oscillate.
4. **Hard revision count limit** — simple, predictable, configurable. The best-scoring draft is used if the limit is reached.
5. **Human-in-the-loop** — pause and ask the user to adjudicate. Breaks the CLI's non-interactive flow.

---

## Decision

The multi-agent evaluation loop is **hard-capped at `MAX_REVISIONS = 3`** iterations.

If the Critic has not accepted the plan by revision 3, the **highest-scoring draft** (by Critic score) is accepted automatically and a **user-visible warning** is emitted.

### Constant definition

```python
# application/agents/orchestrator.py

MAX_REVISIONS: int = 3  # Can be overridden by settings.max_revisions
```

The value is configurable via `settings.max_revisions` (environment variable `ROADMAP_MAX_REVISIONS`) to allow power users or CI environments to adjust. The default of `3` balances quality improvement against cost and latency.

### Orchestrator implementation

```python
# application/agents/orchestrator.py

class OrchestratorAgent:
    def __init__(
        self,
        curriculum_agent: CurriculumAgent,
        critic_agent: CriticAgent,
        max_revisions: int = MAX_REVISIONS,
    ) -> None:
        self._curriculum = curriculum_agent
        self._critic = critic_agent
        self._max_revisions = max_revisions

    def run(self, goal: str, gap_items: list[GapItem]) -> tuple[RoadmapDraft, bool]:
        """
        Returns (best_draft, was_accepted).
        was_accepted=False means the loop hit MAX_REVISIONS without acceptance.
        """
        best_draft: RoadmapDraft | None = None
        best_score: float = -1.0
        feedback: str | None = None

        for revision in range(self._max_revisions):
            draft = self._curriculum.generate(goal, gap_items, feedback=feedback)
            evaluation = self._critic.evaluate(draft)

            if evaluation.score > best_score:
                best_score = evaluation.score
                best_draft = draft

            if evaluation.accepted:
                return best_draft, True

            feedback = evaluation.feedback
            # Log revision attempt for debugging
            logger.info(
                "Revision %d/%d rejected. Score: %.2f. Feedback: %s",
                revision + 1,
                self._max_revisions,
                evaluation.score,
                evaluation.feedback[:200],
            )

        # Loop exhausted — return best draft with warning flag
        return best_draft, False
```

### User-facing behaviour when limit is reached

When `was_accepted=False`:

```
⚠  Warning: The roadmap quality loop reached its revision limit (3/3) without
   the Critic Agent accepting the plan. The best-scoring draft has been used.
   Score: 0.71/1.00

   You can re-run with --regenerate to try again, or edit the roadmap manually
   with: roadmap edit --id <id>
```

The roadmap is saved to the database with `revision_count = MAX_REVISIONS` and a `quality_warning = True` flag, enabling future tooling to identify roadmaps that may benefit from manual review.

### Critic scoring rubric

The Critic Agent evaluates drafts on:

| Criterion | Weight | Description |
|---|---|---|
| Topological correctness | 25% | Skills are in a valid learning order |
| Completeness | 25% | All gap items are covered by at least one milestone |
| Time-box reasonableness | 20% | No single milestone exceeds 40 hours |
| Resource quality | 15% | Resources are relevant, current, and free-available ratio > 50% |
| Goal alignment | 15% | The final milestone directly addresses the stated goal |

A score ≥ 0.85 triggers automatic acceptance. This threshold is configurable via `settings.critic_acceptance_threshold`.

---

## Consequences

### Positive

- **Predictable cost** — with `MAX_REVISIONS = 3`, the maximum LLM token cost for the agent loop is bounded. A roadmap with a 20-skill graph costs at most ~4× the token cost of a single-pass generation.
- **Predictable latency** — worst-case time for the agent loop is `MAX_REVISIONS × (LLM_latency + search_latency)` ≈ 3 × 15 s = 45 s. Users see a progress indicator.
- **No infinite loops** — the system always terminates. This is a hard guarantee, not a probabilistic one.
- **Graceful degradation** — even when the limit is reached, the user receives a usable roadmap (the best draft) rather than an error.
- **Transparency** — the user is informed when the limit was reached, giving them agency to regenerate or manually edit.
- **Configurable** — teams or users who want higher quality and are willing to pay more API cost can increase `MAX_REVISIONS` via environment variable.

### Negative

- **3 revisions may not be enough** — for highly complex goals, the optimal plan may require more than 3 iterations to emerge. Power users can increase the limit, but the default may disappoint on very ambitious goals.
- **Best-score fallback is heuristic** — the Critic's score is itself an LLM output, potentially biased. A draft with a high Critic score may still be suboptimal by an objective human standard.
- **No cross-session learning** — each invocation starts fresh. The loop does not remember that a particular revision pattern worked well for similar goals in past sessions. Addressed in future work via few-shot examples derived from accepted roadmaps.
- **Feedback quality degrades at revision limit** — later revisions receive increasingly specific feedback, which can cause overfitting to Critic preferences rather than genuine improvement. Monitoring the `revision_count` distribution across generated roadmaps will inform future tuning.

### Monitoring

The following metrics are logged per roadmap generation:

- `revision_count` — number of revisions performed (0–`MAX_REVISIONS`).
- `was_accepted` — whether the Critic accepted the final plan.
- `final_critic_score` — score of the accepted/fallback draft.
- `total_agent_latency_s` — wall-clock time for the entire loop.

These are stored in the `roadmaps` table and can be queried to tune the `MAX_REVISIONS` default and the `critic_acceptance_threshold` over time.
