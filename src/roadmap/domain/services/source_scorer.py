"""
Domain service: SourceScorer.

Computes a deterministic reliability score in [0.0, 1.0] for an evidence source.
Explicitly models:
  - Authority: based on source type (official docs, career page, curriculum vs blog)
  - Freshness: decay over time based on publication date
  - Domain trust: recognized reputable domains get a boost
"""

from __future__ import annotations

from datetime import UTC, datetime

from roadmap.domain.entities.source import Source
from roadmap.domain.value_objects import SourceType

# Known authoritative base domains
AUTHORITATIVE_DOMAINS: set[str] = {
    "docs.python.org",
    "developer.mozilla.org",
    "learn.microsoft.com",
    "docs.unrealengine.com",
    "docs.unity3d.com",
    "github.com",
    "arxiv.org",
    "acm.org",
    "ieee.org",
    "mit.edu",
    "stanford.edu",
    "harvard.edu",
    "cmu.edu",
    "coursera.org",
    "edx.org",
}

# Base weight by source type
SOURCE_TYPE_BASE_SCORES: dict[SourceType, float] = {
    SourceType.OFFICIAL_DOCUMENTATION: 0.95,
    SourceType.OFFICIAL_DOCS: 0.95,
    SourceType.UNIVERSITY_CURRICULUM: 0.90,
    SourceType.UNIVERSITY: 0.90,
    SourceType.COMPANY_CAREER_PAGE: 0.90,
    SourceType.JOB_POSTING: 0.85,
    SourceType.INDUSTRY_REPORT: 0.80,
    SourceType.SURVEY: 0.80,
    SourceType.PAPER: 0.85,
    SourceType.BOOK: 0.80,
    SourceType.GITHUB: 0.75,
    SourceType.COURSE: 0.70,
    SourceType.TECHNICAL_ARTICLE: 0.60,
    SourceType.ARTICLE: 0.60,
    SourceType.OTHER: 0.50,
}


class SourceScorer:
    """Deterministic source reliability scoring."""

    @staticmethod
    def score(source: Source) -> float:
        """
        Calculate composite reliability score.
        Formula:
          base_score (by type)
          + domain_bonus (+0.05 if in authoritative list)
          - freshness_penalty (if older than 2 years or 4 years)
        Clamped to [0.1, 1.0].
        """
        base = SOURCE_TYPE_BASE_SCORES.get(source.source_type, 0.50)

        # Domain bonus
        domain_norm = source.domain.lower().removeprefix("www.")
        domain_bonus = 0.05 if any(d in domain_norm for d in AUTHORITATIVE_DOMAINS) else 0.0

        # Freshness multiplier/penalty
        freshness_penalty = 0.0
        if source.published_at is not None:
            now = datetime.now(UTC)
            pub_date = source.published_at if source.published_at.tzinfo else source.published_at.replace(tzinfo=UTC)
            age_years = max(0.0, (now - pub_date).total_seconds() / (365.25 * 86400))
            if age_years > 5.0:
                freshness_penalty = 0.25
            elif age_years > 3.0:
                freshness_penalty = 0.15
            elif age_years > 2.0:
                freshness_penalty = 0.05

        composite = base + domain_bonus - freshness_penalty
        return max(0.1, min(1.0, round(composite, 2)))
