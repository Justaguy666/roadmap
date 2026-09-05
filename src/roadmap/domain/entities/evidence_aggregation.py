"""Domain entities for evidence aggregation, market observation, and decision modeling."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from roadmap.domain.value_objects import Priority, SourceType
from roadmap.shared.ids import new_id


class SkillEvidenceSummary(BaseModel):
    """Aggregated evidence metrics for a single skill."""

    skill_name: str
    evidence_count: int = 0
    unique_source_count: int = 0
    weighted_score: float = Field(default=0.0, ge=0.0, le=1.0)
    average_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    average_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    average_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness_factor: float = Field(default=1.0, ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    supporting_domains: list[str] = Field(default_factory=list)
    supporting_source_types: list[SourceType] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    divergence_notes: list[str] = Field(default_factory=list)


class MarketObservation(BaseModel):
    """Observed market data from job postings and career sources."""

    skill_name: str
    sample_size: int = Field(ge=1)
    mentions: int = Field(ge=0)
    observed_frequency: float = Field(ge=0.0, le=1.0)
    is_observed_sample: Literal[True] = True
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    unique_companies: list[str] = Field(default_factory=list)
    market_regions: list[str] = Field(default_factory=list)
    role_mentions: dict[str, int] = Field(default_factory=dict)
    insufficient_sample: bool = False


class SkillDecisionFactors(BaseModel):
    """Deterministic score components for skill prioritization."""

    market_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    goal_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    skill_gap: float = Field(default=0.0, ge=0.0, le=1.0)
    prerequisite_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    portfolio_value: float = Field(default=0.0, ge=0.0, le=1.0)
    time_cost_factor: float = Field(default=0.5, ge=0.0, le=1.0)


class SkillDecision(BaseModel):
    """Detailed deterministic decision regarding skill inclusion/priority."""

    id: str = Field(default_factory=new_id)
    skill_name: str
    decision: Literal["include", "postpone", "exclude"]
    priority: Priority = Priority.MEDIUM
    composite_score: float = Field(ge=0.0, le=1.0)
    factors: SkillDecisionFactors = Field(default_factory=SkillDecisionFactors)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    rationale: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoadmapQualityScore(BaseModel):
    """Deterministic multi-dimensional quality assessment for a roadmap."""

    overall_score: float = Field(ge=0.0, le=100.0, description="Overall score out of 100")
    goal_alignment: float = Field(ge=0.0, le=100.0)
    market_alignment: float = Field(ge=0.0, le=100.0)
    evidence_strength: float = Field(ge=0.0, le=100.0)
    dependency_correctness: float = Field(ge=0.0, le=100.0)
    time_feasibility: float = Field(ge=0.0, le=100.0)
    portfolio_value: float = Field(ge=0.0, le=100.0)
    scope_efficiency: float = Field(ge=0.0, le=100.0)
    scoring_notes: list[str] = Field(default_factory=list)
