"""API schemas for Profile endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from roadmap.domain.value_objects import BudgetPreference, SkillLevel


class ProfileCreateRequest(BaseModel):
    """Request body for POST /api/v1/profiles."""

    name: str = Field(min_length=1, max_length=100, description="Display name")
    target_goal: str = Field(
        min_length=5,
        max_length=500,
        description="Career or learning goal, e.g. 'Become a Game Programmer'",
    )
    target_role: str = Field(default="", max_length=200, description="Specific target role title")
    current_level: SkillLevel = Field(default=SkillLevel.MISSING, description="Self-assessed skill level")
    current_skills: list[str] = Field(default_factory=list, description="Skills the user already has")
    programming_languages: list[str] = Field(default_factory=list)
    previous_experience: str = Field(default="", max_length=1000)
    completed_projects: list[str] = Field(default_factory=list)
    preferred_technologies: list[str] = Field(default_factory=list)
    preferred_industry: str = Field(default="", max_length=200)
    target_markets: list[str] = Field(default_factory=list)
    learning_preferences: list[str] = Field(default_factory=list)
    budget: BudgetPreference = Field(default=BudgetPreference.ANY)
    constraints: list[str] = Field(default_factory=list)
    study_hours_per_day: float = Field(default=2.0, gt=0, le=24)
    deadline_months: int = Field(default=12, gt=0, le=120)


class ProfileResponse(BaseModel):
    """Response body for profile endpoints."""

    id: str
    name: str
    target_goal: str
    target_role: str
    current_level: str
    current_skills: list[str]
    programming_languages: list[str]
    previous_experience: str
    completed_projects: list[str]
    preferred_technologies: list[str]
    preferred_industry: str
    target_markets: list[str]
    learning_preferences: list[str]
    budget: str
    constraints: list[str]
    study_hours_per_day: float
    deadline_months: int
    created_at: datetime
    updated_at: datetime
