"""Domain entities: Source, Evidence, and Recommendation.

The evidence system ensures every recommendation is traceable
to a concrete source (job posting, article, documentation, etc.).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from roadmap.domain.value_objects import SourceType
from roadmap.shared.ids import new_id


class Source(BaseModel):
    """
    An evidence source — a URL that was retrieved and analyzed.

    Sources are deduplicated by URL.
    Reliability scoring helps down-weight low-quality sources.
    """

    id: str = Field(default_factory=new_id)
    url: str = Field(min_length=1, max_length=2000)
    title: str = Field(default="", max_length=500)
    source_type: SourceType = Field(default=SourceType.OTHER)
    publisher: str = Field(default="", max_length=200)
    domain: str = Field(default="", max_length=200, description="e.g. 'github.com'")

    # Timestamps
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = Field(
        default=None,
        description="Publication/last-update date if available",
    )

    # Quality
    reliability_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Assessed source reliability (0=unreliable, 1=authoritative)",
    )
    content_hash: str = Field(
        default="",
        description="SHA-256 of retrieved content, used for change detection",
    )

    @property
    def is_fresh(self) -> bool:
        """True if the source was published or updated within 2 years."""
        if self.published_at is None:
            return True  # assume fresh if unknown
        age_years = (datetime.now(UTC) - self.published_at).days / 365
        return age_years <= 2.0

    @property
    def is_authoritative(self) -> bool:
        return self.reliability_score >= 0.8


class Evidence(BaseModel):
    """
    A specific claim extracted from a Source.

    Evidence items are attached to skills and recommendations to make
    the system's decisions traceable and explainable.
    """

    id: str = Field(default_factory=new_id)
    source_id: str = Field(description="ID of the Source this was extracted from")

    extracted_claim: str = Field(
        min_length=5,
        max_length=2000,
        description="The exact claim extracted from the source",
    )
    relevance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How relevant this claim is to the user's goal (0–1)",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence that the extraction is accurate (0–1)",
    )
    associated_skill_names: list[str] = Field(
        default_factory=list,
        description="Skill names this evidence supports",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.8 and self.relevance >= 0.7


class Recommendation(BaseModel):
    """
    A recorded decision about a skill — include, postpone, or exclude.

    Linked to evidence items to support the `roadmap why <skill>` command.
    """

    id: str = Field(default_factory=new_id)
    skill_id: str = Field(description="The skill this recommendation is about")
    roadmap_id: str = Field(description="The roadmap this decision belongs to")

    decision: str = Field(
        description="One of: 'include', 'postpone', 'exclude'",
        pattern=r"^(include|postpone|exclude)$",
    )
    reasoning: str = Field(
        min_length=10,
        max_length=2000,
        description="Human-readable explanation of the decision",
    )
    decision_factors: list[str] = Field(
        default_factory=list,
        description="Key factors that drove this decision",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of Evidence items that support this decision",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Agent's confidence in this recommendation (0–1)",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_included(self) -> bool:
        return self.decision == "include"

    @property
    def is_postponed(self) -> bool:
        return self.decision == "postpone"


