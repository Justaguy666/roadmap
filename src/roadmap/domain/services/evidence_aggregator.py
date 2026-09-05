"""Domain service: EvidenceAggregator.

Aggregates discrete evidence records and canonical sources into a coherent
evidence summary for each skill. Uses deterministic mathematical weighting:

EvidenceWeight = source_reliability * evidence_relevance * evidence_confidence * freshness_factor
Normalized to [0, 1].
"""

from __future__ import annotations

from datetime import UTC, datetime

from roadmap.domain.entities.evidence_aggregation import SkillEvidenceSummary
from roadmap.domain.entities.source import Evidence, Source
from roadmap.domain.value_objects import SourceType


class EvidenceAggregator:
    """Aggregates and weights evidence records per skill."""

    @staticmethod
    def aggregate_for_skill(
        skill_name: str,
        evidence_items: list[Evidence],
        sources_by_id: dict[str, Source],
    ) -> SkillEvidenceSummary:
        """Calculate weighted summary for a single skill."""
        norm_name = skill_name.strip().lower()
        matching_evidence = [
            e for e in evidence_items
            if any(s.strip().lower() == norm_name for s in e.associated_skill_names)
        ]

        if not matching_evidence:
            return SkillEvidenceSummary(
                skill_name=skill_name,
                evidence_count=0,
                unique_source_count=0,
                weighted_score=0.0,
            )

        unique_source_ids = {e.source_id for e in matching_evidence if e.source_id in sources_by_id}
        sources = [sources_by_id[sid] for sid in unique_source_ids]

        now = datetime.now(UTC)
        weights: list[float] = []
        relevances: list[float] = []
        confidences: list[float] = []
        reliabilities: list[float] = []
        freshness_factors: list[float] = []

        supporting_domains: set[str] = set()
        supporting_types: set[SourceType] = set()

        for ev in matching_evidence:
            source = sources_by_id.get(ev.source_id)
            if not source:
                continue

            # Freshness factor
            freshness = 1.0
            if source.published_at:
                age_days = max(0, (now - source.published_at).days)
                years = age_days / 365.25
                freshness = max(0.5, 1.0 - (0.10 * years))

            # Raw Evidence Weight formula:
            # reliability * relevance * confidence * freshness
            w = source.reliability_score * ev.relevance * ev.confidence * freshness
            weights.append(w)
            relevances.append(ev.relevance)
            confidences.append(ev.confidence)
            reliabilities.append(source.reliability_score)
            freshness_factors.append(freshness)

            if source.domain:
                supporting_domains.add(source.domain)
            supporting_types.add(source.source_type)

        # Detect divergence / conflicting claims
        divergence_notes: list[str] = []
        contradicting_ids: list[str] = []

        # Check if claims contain strong divergence keywords
        for ev in matching_evidence:
            lower_claim = ev.extracted_claim.lower()
            if any(k in lower_claim for k in ("not recommended", "obsolete", "deprecated", "optional for", "avoid", "legacy")):
                contradicting_ids.append(ev.id)
                divergence_notes.append(f"Caveat/Contradiction noted: '{ev.extracted_claim}'")

        # Weighted aggregate: average of top-quality weights with diminishing returns bonus
        if weights:
            base_score = sum(weights) / len(weights)
            # Bonus for source diversity
            diversity_bonus = min(0.15, len(sources) * 0.03)
            final_weighted = min(1.0, base_score + diversity_bonus)
            avg_rel = sum(relevances) / len(relevances)
            avg_conf = sum(confidences) / len(confidences)
            avg_relib = sum(reliabilities) / len(reliabilities)
            avg_fresh = sum(freshness_factors) / len(freshness_factors)
        else:
            final_weighted = 0.0
            avg_rel = 0.0
            avg_conf = 0.0
            avg_relib = 0.0
            avg_fresh = 1.0

        return SkillEvidenceSummary(
            skill_name=skill_name,
            evidence_count=len(matching_evidence),
            unique_source_count=len(sources),
            weighted_score=round(final_weighted, 3),
            average_relevance=round(avg_rel, 3),
            average_confidence=round(avg_conf, 3),
            average_reliability=round(avg_relib, 3),
            freshness_factor=round(avg_fresh, 3),
            supporting_evidence_ids=[e.id for e in matching_evidence if e.id not in contradicting_ids],
            supporting_domains=sorted(supporting_domains),
            supporting_source_types=sorted(supporting_types, key=lambda t: t.value),
            contradicting_evidence_ids=contradicting_ids,
            divergence_notes=divergence_notes,
        )

    @classmethod
    def aggregate_all(
        cls,
        evidence_items: list[Evidence],
        sources: list[Source],
    ) -> dict[str, SkillEvidenceSummary]:
        """Aggregate evidence for all skills found across evidence records."""
        sources_by_id = {s.id: s for s in sources}
        skills: set[str] = set()
        for ev in evidence_items:
            for s in ev.associated_skill_names:
                skills.add(s.strip())

        summaries: dict[str, SkillEvidenceSummary] = {}
        for sk in sorted(skills):
            summaries[sk] = cls.aggregate_for_skill(sk, evidence_items, sources_by_id)
        return summaries
