"""Domain service: MarketIntelligenceService.

Aggregates observed job-posting evidence into structured market observations,
calculates honest observed sample frequencies, segments by region/role,
and computes deterministic market priorities:

MarketPriority = observed_frequency * source_quality * target_role_relevance
Normalized in [0, 1].
"""

from __future__ import annotations

from collections import defaultdict

from roadmap.domain.entities.evidence_aggregation import MarketObservation
from roadmap.domain.entities.source import Evidence, Source
from roadmap.domain.value_objects import SourceType


class MarketIntelligenceService:
    """Computes deterministic market metrics and segmentations."""

    @staticmethod
    def analyze_market_sample(
        target_role: str,
        evidence_items: list[Evidence],
        sources_by_id: dict[str, Source],
        min_sample_threshold: int = 2,
    ) -> dict[str, MarketObservation]:
        """Aggregate observed market postings and compute frequencies with explicit sample sizes."""
        # Filter for job postings and career pages
        job_sources = {
            sid: s for sid, s in sources_by_id.items()
            if s.source_type in (
                SourceType.JOB_POSTING,
                SourceType.COMPANY_CAREER_PAGE,
                SourceType.INDUSTRY_REPORT,
            )
        }

        # If few or no direct job postings exist, fall back to total sources analyzed
        sample_pool = job_sources if len(job_sources) >= min_sample_threshold else sources_by_id
        sample_size = max(1, len(sample_pool))

        # Track mentions per skill
        skill_evidence_map: dict[str, list[Evidence]] = defaultdict(list)
        for ev in evidence_items:
            if ev.source_id in sample_pool:
                for s in ev.associated_skill_names:
                    skill_evidence_map[s.strip()].append(ev)

        observations: dict[str, MarketObservation] = {}
        for skill, ev_list in skill_evidence_map.items():
            # Deduplicate by source_id
            unique_source_ids = {e.source_id for e in ev_list}
            mentions = len(unique_source_ids)
            freq = round(min(1.0, mentions / sample_size), 3)

            # Extract companies and domains
            companies: set[str] = set()
            regions: set[str] = set()
            for sid in unique_source_ids:
                src = sample_pool[sid]
                if src.publisher:
                    companies.add(src.publisher)
                elif src.domain:
                    # Strip www. and tld for company name guess
                    parts = src.domain.split(".")
                    if len(parts) >= 2:
                        companies.add(parts[-2].capitalize())

                # Check URL / domain for country codes
                if ".vn" in src.domain or "vietnam" in src.url.lower():
                    regions.add("Vietnam")
                elif ".jp" in src.domain or "japan" in src.url.lower():
                    regions.add("Japan")
                elif ".us" in src.domain or ".com" in src.domain:
                    regions.add("Global / US")

            observations[skill] = MarketObservation(
                skill_name=skill,
                sample_size=sample_size,
                mentions=mentions,
                observed_frequency=freq,
                supporting_evidence_ids=[e.id for e in ev_list],
                unique_companies=sorted(companies),
                market_regions=sorted(regions) if regions else ["General"],
                role_mentions={target_role: mentions},
                insufficient_sample=(sample_size < min_sample_threshold),
            )

        return observations

    @staticmethod
    def compute_market_priority(
        observation: MarketObservation | None,
        source_quality: float = 0.85,
        target_role_relevance: float = 0.90,
    ) -> float:
        """
        Compute deterministic market priority.

        Formula:
        MarketPriority = observed_frequency * source_quality * target_role_relevance
        """
        if not observation or observation.insufficient_sample:
            return 0.30  # Baseline default when market data is absent or thin

        score = observation.observed_frequency * source_quality * target_role_relevance
        return round(min(1.0, max(0.0, score)), 3)
