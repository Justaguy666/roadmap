"""Domain entity: Goal and Competency.

A Goal is the structured, analyzed form of the user's raw target statement.
A Competency is a high-level capability area within a goal.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from roadmap.shared.ids import new_id


class Competency(BaseModel):
    """
    A high-level capability area required to achieve a goal.

    Example: For 'Game Programmer', competencies might be:
      - Programming Fundamentals
      - Mathematics
      - Game Engine Mastery
      - Computer Graphics
    """

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    importance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How important this competency is to the goal (0–1)",
    )
    skill_names: list[str] = Field(
        default_factory=list,
        description="Skill names belonging to this competency",
    )


class Goal(BaseModel):
    """
    Structured representation of the user's career/learning goal.

    Raw user input is transformed into a structured Goal by the
    Goal Analysis use case (MVP-2+). In MVP-1, Goals can be
    created manually or with minimal analysis.
    """

    id: str = Field(default_factory=new_id)
    profile_id: str = Field(description="ID of the owning UserProfile")

    # Raw and structured
    raw_goal: str = Field(
        min_length=5,
        max_length=500,
        description="Original user input",
    )
    target_role: str = Field(
        default="",
        max_length=200,
        description="Resolved role title",
    )
    context: str = Field(
        default="",
        max_length=2000,
        description="Structured context about this goal (produced by LLM analysis)",
    )

    # Structured breakdown
    competencies: list[Competency] = Field(default_factory=list)
    required_skill_names: list[str] = Field(
        default_factory=list,
        description="Top-level skill names identified for this goal",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Key assumptions made during goal analysis",
    )

    # Metadata
    analyzed_at: datetime | None = Field(
        default=None,
        description="When LLM analysis was performed; None if not yet analyzed",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_analyzed(self) -> bool:
        """True if LLM goal analysis has been performed."""
        return self.analyzed_at is not None

    def mark_analyzed(self) -> None:
        self.analyzed_at = datetime.now(UTC)

