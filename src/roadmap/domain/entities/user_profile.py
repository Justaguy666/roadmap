"""Domain entity: UserProfile.

Represents everything the system needs to know about the user.
Pure Python / Pydantic — no database or external library imports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from roadmap.domain.value_objects import BudgetPreference, SkillLevel
from roadmap.shared.ids import new_id


class UserProfile(BaseModel):
    """
    Persistent user profile.

    Contains the user's goal, current skills, constraints, and preferences.
    This is the primary input to every agent in the system.
    """

    # Identity
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1, max_length=100)

    # Goal
    target_goal: str = Field(
        min_length=5,
        max_length=500,
        description="Raw goal statement, e.g. 'Become a Game Programmer'",
    )
    target_role: str = Field(
        default="",
        max_length=200,
        description="Specific role title, e.g. 'Gameplay Programmer'",
    )

    # Current state
    current_level: SkillLevel = Field(
        default=SkillLevel.MISSING,
        description="Overall self-assessed skill level",
    )
    current_skills: list[str] = Field(
        default_factory=list,
        description="List of skill names the user already has",
    )
    programming_languages: list[str] = Field(
        default_factory=list,
        description="Programming languages the user knows",
    )
    previous_experience: str = Field(
        default="",
        max_length=1000,
        description="Brief description of relevant work or project experience",
    )
    completed_projects: list[str] = Field(
        default_factory=list,
        description="Notable projects the user has already completed",
    )

    # Preferences
    preferred_technologies: list[str] = Field(
        default_factory=list,
        description="Technologies the user prefers to work with",
    )
    preferred_industry: str = Field(
        default="",
        max_length=200,
        description="Target industry, e.g. 'Game Development'",
    )
    target_markets: list[str] = Field(
        default_factory=list,
        description="Geographic job markets, e.g. ['Vietnam', 'Japan']",
    )
    learning_preferences: list[str] = Field(
        default_factory=list,
        description="Preferred learning styles, e.g. ['video', 'hands-on', 'book']",
    )
    budget: BudgetPreference = Field(
        default=BudgetPreference.ANY,
        description="Willingness to pay for learning resources",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Any hard constraints, e.g. 'no bootcamps', 'English only'",
    )

    # Time constraints
    study_hours_per_day: Annotated[float, Field(gt=0, le=24)] = Field(
        default=2.0,
        description="Available study hours per day",
    )
    deadline_months: Annotated[int, Field(gt=0, le=120)] = Field(
        default=12,
        description="Months until target deadline",
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("current_skills", "programming_languages", mode="before")
    @classmethod
    def strip_empty_strings(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s.strip()]

    @field_validator("target_markets", mode="before")
    @classmethod
    def strip_markets(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s.strip()]

    @property
    def study_hours_per_week(self) -> float:
        return self.study_hours_per_day * 5  # assuming 5-day study week

    @property
    def total_available_hours(self) -> float:
        """Rough upper bound on total study hours before deadline."""
        weeks = self.deadline_months * 4.33
        return weeks * self.study_hours_per_week

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    model_config = {"use_enum_values": False}

