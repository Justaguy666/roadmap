"""API schemas for Roadmap endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MilestoneResponse(BaseModel):
    id: str
    name: str
    description: str
    exit_criteria: list[str]
    estimated_weeks: float
    is_achieved: bool


class PhaseResponse(BaseModel):
    id: str
    phase_number: int
    name: str
    objective: str
    estimated_weeks: float
    skill_names: list[str] = Field(default_factory=list)
    milestones: list[MilestoneResponse] = Field(default_factory=list)


class RoadmapSummaryResponse(BaseModel):
    """Lightweight roadmap list item — no phases."""

    id: str
    profile_id: str
    title: str
    version: int
    objective: str
    quality_score: float
    validation_status: str
    generated_at: datetime
    last_updated_at: datetime


class RoadmapResponse(BaseModel):
    """Full roadmap with phases and milestones."""

    id: str
    profile_id: str
    title: str
    version: int
    objective: str
    quality_score: float
    validation_status: str
    generated_at: datetime
    last_updated_at: datetime
    phases: list[PhaseResponse] = Field(default_factory=list)
