"""Pydantic schema for LLM Adaptation Proposal."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillAdjustmentDraft(BaseModel):
    """Adjustments to a specific skill (e.g., re-allocating hours or shifting phase)."""

    skill_name: str = Field(description="Name of the affected skill")
    action: str = Field(
        default="REVISE_HOURS",
        description="'REVISE_HOURS', 'SPLIT_SUB_SKILLS', 'POSTPONE', 'ADD_PREREQUISITE', or 'REORDER'",
    )
    new_estimated_hours: float | None = Field(default=None, description="Updated hour estimate if changed")
    new_phase_number: int | None = Field(default=None, description="Target phase number if shifted")
    rationale: str = Field(description="Detailed reason for this specific skill adjustment")


class PhaseAdjustmentDraft(BaseModel):
    """Adjustments to phase duration or structure."""

    phase_number: int = Field(description="Phase number being modified")
    new_estimated_weeks: float = Field(description="Updated duration in weeks")
    rationale: str = Field(description="Reason for duration adjustment")


class SupportSkillDraft(BaseModel):
    """A supporting or remedial skill proposed to bridge a blocker or skill gap."""

    name: str = Field(description="Skill name")
    category: str = Field(default="foundations", description="Skill category")
    target_phase_number: int = Field(description="Phase to insert this skill into")
    estimated_hours: float = Field(default=15.0, description="Hours required")
    rationale: str = Field(description="Why this skill helps resolve current blocker")


class AdaptationProposal(BaseModel):
    """
    Structured proposal produced by the AdaptationAgent.
    """

    adaptation_strategy: str = Field(
        description="High-level strategy summary (e.g. 'Pace recalibration and remedial math support')",
    )
    rationale: str = Field(
        description="Justification based on logged hours, velocity, and user feedback",
    )
    affected_phase_numbers: list[int] = Field(
        default_factory=list,
        description="List of phase numbers modified",
    )
    phase_adjustments: list[PhaseAdjustmentDraft] = Field(
        default_factory=list,
        description="Adjustments to phase durations",
    )
    skill_adjustments: list[SkillAdjustmentDraft] = Field(
        default_factory=list,
        description="Adjustments to existing skills",
    )
    support_skills: list[SupportSkillDraft] = Field(
        default_factory=list,
        description="Remedial/support skills to introduce",
    )
    estimated_total_weeks_delta: float = Field(
        default=0.0,
        description="Net change in total roadmap weeks (positive for extension)",
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score for this adaptation plan",
    )
