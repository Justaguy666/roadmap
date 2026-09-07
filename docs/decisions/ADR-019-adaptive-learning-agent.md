# ADR-019: Adaptive Learning Agent (Progress Tracking, Feedback & Replanning)

## Status
Accepted

## Context
In RoadmapAI MVP-1 through MVP-4.1, the application produced high-quality, evidence-backed, validated static learning roadmaps. However, learning is rarely static:
1. Learners encounter difficult concepts or blockers causing schedule slip.
2. Learners master certain skills faster or slower than initially estimated.
3. Users need a way to record granular progress, actual hours spent, and qualitative feedback (difficulty, confidence, blockers).
4. When significant schedule deviations occur, the system needs an automated mechanism to recalibrate without blindly rewriting or corrupting completed competencies.
5. In accordance with RoadmapAI's core architectural guidelines, LLMs must never directly mutate the database, must operate within deterministic budget limits, and proposed adaptations must pass graph and schedule validation before user confirmation.

## Decision

We introduced the **MVP-5 Adaptive Learning Agent Architecture**:

1. **Domain Data Model**:
   - `ProgressRecord`: Tracks `status` (`NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `SKIPPED`), `completion_percentage` (0-100%), `planned_hours`, `actual_hours`, `started_at`, and `completed_at`.
   - `LearningFeedback`: Captures qualitative ratings (1-5 for `difficulty`, `confidence`, `satisfaction`), explicit `blocked_reason`, and open-ended observations.
   - `DeviationReport`: Evaluates learning velocity, schedule slip, and blockers. Classifies schedule health into `ON_TRACK`, `WARNING`, and `CRITICAL`.
   - `RoadmapAdaptation`: An immutable audit record linking `vN` to `vN+1`, detailing trigger reasons, deviation summaries, and structured changes.

2. **Deterministic Deviation Detection & Anti-Oscillation Guard**:
   - `DeviationDetector` calculates pure deterministic metrics:
     - Velocity ratio: $\frac{\text{planned hours completed}}{\text{actual hours spent}}$
     - Progress deviation: $\max(0, \text{expected percent} - \text{actual percent})$
     - Warning threshold: $\ge 20\%$ deviation or 1 blocked skill or velocity $< 0.75\text{x}$.
     - Critical threshold: $\ge 40\%$ deviation, multiple blocked skills, or velocity $\le 0.50\text{x}$.
   - **No LLM calls** when `ON_TRACK`.
   - **Anti-Oscillation Policy**: Requires a minimum threshold of actual study hours (default 10h) between adaptations to prevent rapid schedule thrashing, with `--force` override available for user-driven replanning.

3. **Controlled LLM Adaptation Agent**:
   - Added `LLMWorkflow.ADAPTATION` governed by `llm_adaptation_budget` (default 5 requests/day).
   - `AdaptationAgent` returns a strictly structured `AdaptationProposal` Pydantic model (`phase_adjustments`, `skill_adjustments`, `support_skills`).
   - The LLM never writes to the database.

4. **Deterministic Validation Loop & Confirmation Gate**:
   - All candidate adaptations are verified through `SkillGraphValidator` (NetworkX DAG cycle and prerequisite order check).
   - Completed skills are immutable and preserved.
   - The user is presented with a clear proposal summary and diff before confirming persistence.
   - Persisting creates an immutable new version (`vN+1`), preserving historical versions for audit and comparison.

5. **CLI Interface**:
   - `roadmap progress`: Dashboard showing phase progress bars, skill status, actual vs planned hours, velocity ratio, and schedule health.
   - `roadmap progress update <skill>`: Record progress percentage, actual hours, status, and notes.
   - `roadmap feedback`: Record qualitative feedback and blockers.
   - `roadmap adapt`: Analyze progress, propose minimal adaptations, prompt for confirmation, and save `vN+1`.
   - `roadmap history`: View all historical roadmap versions and adaptation triggers.
   - `roadmap why-change [version]`: Inspect detailed rationale and modification diffs between versions.

## Consequences

### Positive
- **Closed-Loop Adaptation**: Transforms RoadmapAI from a static planner into a reactive, adaptive personal tutor.
- **Data Integrity**: Historical roadmaps remain immutable. Adaptations are auditable and traceable.
- **Budget Control**: LLM calls are strictly avoided during normal progression; only invoked when critical deviations warrant replanning.
- **Safety**: Cyclic dependencies or invalid prerequisites proposed by an LLM are caught deterministically prior to persistence.

### Negative
- Additional database tables and migration overhead (`learning_feedbacks`, `roadmap_adaptations`).
- Requires learners to record hours or progress updates to benefit from adaptive features.
