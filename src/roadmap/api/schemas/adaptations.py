"""API schemas for Adaptation endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DeviationReportResponse(BaseModel):
    """Serialised DeviationReport from the adaptation use case."""

    roadmap_id: str
    profile_id: str
    status: str
    total_planned_hours: float
    total_actual_hours: float
    expected_completion_percentage: float
    actual_completion_percentage: float
    velocity_ratio: float
    progress_deviation: float
    blocked_skills: list[str]
    behind_skills: list[str]
    issues: list[str]
    recommendations: list[str]
    analyzed_at: datetime
    requires_adaptation: bool


class AdaptationProposalResponse(BaseModel):
    """
    Proposal returned by POST /adaptations/prepare.

    IMPORTANT: This is a read-only proposal.
    It does NOT automatically persist a new roadmap version.
    Approval/persistence is a separate operation (MVP-7.3+).
    """

    profile_id: str
    deviation_report: DeviationReportResponse
    adaptation_needed: bool = Field(
        description="Whether the deviation analysis recommends replanning"
    )
    proposal_summary: str = Field(
        description="LLM-generated or deterministic summary of proposed changes"
    )
    proposed_changes: list[str] = Field(
        default_factory=list,
        description="Itemised list of proposed modifications",
    )
    anti_oscillation_blocked: bool = Field(
        default=False,
        description="True if anti-oscillation guard prevented proposal generation",
    )
    message: str = Field(
        default="",
        description="Additional context or instructions for the caller",
    )
