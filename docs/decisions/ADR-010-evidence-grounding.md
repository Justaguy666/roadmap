# ADR-010: Evidence Grounding and Traceability

## Status
Accepted

## Context
AI-generated learning roadmaps frequently hallucinate obsolete skills, misrepresent industry standards, or propose curricula without verifiable justification. The user cannot distinguish between genuine industry demands and model guesses.

## Decision
Establish first-class domain models for **Evidence Grounding**:
1. `Source`: Represents the origin document/URL, enriched with canonical URL normalization and deterministic reliability scoring (`SourceScorer`).
2. `Evidence`: Represents discrete extracted claims tied back to a `source_id`.
3. `RoadmapSkillDraft` and domain `Skill` explicitly store `evidence_ids`.
4. Users can inspect all underlying sources via `roadmap sources` or filtered by skill via `roadmap sources --skill <name>`.

## Consequences
- **Positive**: Every recommendation is auditable and grounded in verifiable sources; builds high user trust.
- **Negative**: Adds database tables and storage overhead for storing crawled source snippets and evidence metadata.
