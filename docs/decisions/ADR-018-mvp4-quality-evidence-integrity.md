# ADR-018: MVP-4.1 Quality, Evidence & Decision Integrity Audit

## Status
Accepted

## Context
During MVP-4 end-to-end runs with real LLMs (Gemini 2.5/3.5/3.7), the generation and revision pipeline succeeded functionally, but several data integrity, scoring, and UI explanation discrepancies surfaced:

1. **Missing Recommendation Rationale (`roadmap why <skill>`)**:
   Querying skills such as `Version Control (Git)` or `C++` returned 'No explicit decision factors found' even though candidate generation succeeded and recommendations were persisted in the database.
2. **Evidence ID Alignment & Synthetic LLM IDs**:
   The LLM frequently generates descriptive skill titles (`C++ Programming`, `Version Control (Git)`) or hallucinates pseudo-UUIDs instead of referencing the persisted `EvidenceModel.id` records gathered during research.
3. **Quality Score Discrepancy (60.2 vs 82)**:
   The user noticed an apparent contradiction: the Evaluator agent scored the candidate at 82/100, but the final persisted quality score was 60.2/100.
4. **Silent Acceptance of Degraded Generation States**:
   When the revision loop exhausted its allowed iteration or budget limit while the Evaluator agent returned a REVISE verdict, the system persisted the roadmap anyway and displayed normal success messaging without indicating the incomplete validation state.
5. **Skill Dependency Graph DAG Integrity**:
   Over-constrained linear prerequisite chains could be proposed by the LLM instead of natural branching DAGs where parallel foundations can be acquired concurrently.

## Decision

### 1. Robust Skill & Evidence Identity Resolution
- In `SqliteRecommendationRepository.find_by_skill_name_or_id`: Joined `skills` table to match not only on exact skill ID, but on exact skill name, case-insensitive name, and substring aliases (e.g. searching `C++` finds `C++ Programming`).
- In `EvidenceAggregator.find_evidence_summary`: Introduced normalized matching between descriptive roadmap skill titles and canonical research terms:
  - Exact match -> case-insensitive match -> normalized alphanumeric keyword matching (preserving `C++` tokens and stripping parenthesized qualifiers like `(Git)`) -> attached evidence ID set intersection.
- In `GenerateRoadmapUseCase._to_domain_roadmap`: Validated all proposed `evidence_ids` against persisted DB `EvidenceModel` records. Invalid or synthetic LLM IDs are dropped and replaced with the matching canonical evidence summary's `supporting_evidence_ids`.

### 2. Disentangling Evaluator Critique vs Deterministic Quality Score
- **LLM Evaluator Score (0-100)**: Qualitative pedagogical assessment returned by `RoadmapEvaluator` based on role fit, difficulty progression, and pacing.
- **Deterministic Quality Score (0-100)**: Quantitative mathematical score computed across 7 weighted dimensions by `QualityScorer` (Goal Alignment 20%, Market Alignment 20%, Evidence Strength 15%, Dependency Correctness 15%, Time Feasibility 15%, Portfolio Value 10%, Scope Efficiency 5%).
- When skill name normalization was missing, grounded skill lookup failed (`market_alignment = 0.0`, `evidence_strength = 0.0`), driving the deterministic score down to 60.2. With normalized evidence matching, grounded skills are correctly identified (90.8/100).
- CLI commands (`generate`, `show`) now explicitly label both metrics separately:
  - `Deterministic Quality: 90.8/100`
  - `Evaluator Score: 82.0/100 (REVISE)`

### 3. Explicit Degraded State & Validation Status Persistence
- Added `validation_status: str` (values: `COMPLETED`, `COMPLETED_WITH_WARNINGSb), `evaluator_score: float | None`, and `evaluator_verdict: str | None` to the `Roadmap` domain entity and `roadmaps` database table.
- When the revision loop terminates due to budget or cycle exhaustion while the evaluator returned REVISE or deterministic validation warnings remain, `validation_status` is set to `COMPLETED_WITH_WARNINGS`.
- The CLI displays prominent warning banners:
  `⚠ Validation completed with warnings / degraded state: revision budget or cycle limit reached (Evaluator critique score: 82/100, verdict: REVISE).

### 4. Transparent Decision Factor Breakdown in CLI
- Formatted `roadmap why <skill>` with a structured table displaying:
  - Factor dimensions: Market Relevance (25%), Goal Relevance (30%), Skill Gap (20%), Prerequisite Importance (15%), Portfolio Value (10%), Time Cost Factor (feasibility).
  - Raw score, weight percentage, weighted contribution, and descriptive interpretation.
  - Final composite score and deterministic threshold explanation (>= 0.45 include, >= 0.70 high priority).
  - Supporting evidence citations resolving to real source domains and extracted claims.

3## 5. Skill Graph DAG Guidance
- Refined generation system prompts to instruct the LLM to specify direct technical prerequisites only, preventing artificial single-file linear chains and permitting concurrent foundational skill acquisition.

3# Consequences
- **Positive**: Complete traceability between market research evidence, skill recommendations, and CLI explanations.
- **Positive**: No more mysterious 0% evidence grounding or false quality penalties due to string mismatches.
- **Positive**: Transparent user feedback when roadmap generation finishes under constrained revision budgets.
- **Positive**: Clear distinction between subjective LLM critique scores and deterministic objective quality metrics.