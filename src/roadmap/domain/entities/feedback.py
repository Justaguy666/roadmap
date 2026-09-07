"""Domain entity: LearningFeedback.

Captures qualitative feedback from the learner on difficulty, confidence,
satisfaction, blockers, and open-ended observations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from roadmap.shared.ids import new_id


class LearningFeedback(BaseModel):
    """
    User feedback on a skill, phase, or the overall roadmap.
    """

    id: str = Field(default_factory=new_id)
    profile_id: str = Field(description="Owning profile ID")
    roadmap_id: str = Field(description="Associated roadmap ID")
    skill_id: str | None = Field(default=None, description="Optional target skill ID")
    skill_name: str = Field(default="", description="Denormalized skill name")
    phase_id: str | None = Field(default=None, description="Optional target phase ID")

    difficulty: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Perceived difficulty rating (1=Very Easy, 5=Extremely Hard)",
    )
    confidence: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Self-assessed confidence level (1=Lost, 5=Fully Confident)",
    )
    satisfaction: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Overall satisfaction with materials and pacing (1=Frustrated, 5=Delighted)",
    )
    blocked_reason: str = Field(
        default="",
        max_length=500,
        description="Specific blockers or obstacles preventing progress",
    )
    free_text: str = Field(
        default="",
        max_length=2000,
        description="Open-ended user observations and feedback",
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional additional context",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
