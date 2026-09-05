"""
Structured schemas for Skill Gap Analysis.

Combines the output of Goal Analysis with the user's current baseline
and deterministic domain calculations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from roadmap.domain.value_objects.enums import Priority, SkillLevel


class SkillGapItem(BaseModel):
    """An individual skill gap calculation and explanation."""

    skill: str = Field(min_length=1, max_length=150, description="Skill name")
    category: str = Field(default="general", max_length=100)
    current_level: SkillLevel = Field(description="User's current assessed or reported level")
    target_level: SkillLevel = Field(description="Target level required by the goal")
    gap: int = Field(ge=0, le=4, description="Level gap: target - current (0 means no gap)")
    priority: Priority = Field(description="Deterministic priority score mapped to enum")
    reasoning: str = Field(default="", max_length=500, description="Explanation for this gap and urgency")


class SkillGapAnalysisResult(BaseModel):
    """Aggregated result of comparing current skills against goal requirements."""

    interpreted_goal: str = Field(default="", description="The goal being analyzed")
    target_role: str = Field(default="", description="The target role")
    gaps: list[SkillGapItem] = Field(
        default_factory=list,
        description="All evaluated skills and their current gaps",
    )
    total_gaps: int = Field(default=0, ge=0, description="Total number of skills with level gap > 0")
    critical_gaps_count: int = Field(default=0, ge=0, description="Number of critical priority gaps")
    completion_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of required skills already at or above target level (0.0 to 1.0)",
    )
    summary_notes: list[str] = Field(
        default_factory=list,
        description="High-level insights about the user's current readiness and largest hurdles",
    )
