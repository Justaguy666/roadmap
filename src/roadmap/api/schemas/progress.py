"""API schemas for Progress endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from roadmap.domain.entities.progress_record import ProgressStatus


class ProgressCreateRequest(BaseModel):
    """Request body for POST /api/v1/profiles/{id}/progress."""

    skill_name: str = Field(min_length=1, max_length=200, description="Name of the skill being updated")
    completion_percentage: float = Field(ge=0.0, le=100.0, description="Progress percentage 0-100")
    status: ProgressStatus | None = Field(default=None, description="Optional explicit status override")
    actual_hours: float | None = Field(default=None, ge=0.0, description="Hours spent on this skill")
    notes: str = Field(default="", max_length=1000)


class ProgressResponse(BaseModel):
    """Response body for progress endpoints."""

    id: str
    profile_id: str
    skill_id: str
    skill_name: str
    phase_id: str | None
    status: str
    completion_percentage: float
    planned_hours: float
    actual_hours: float
    started_at: datetime | None
    completed_at: datetime | None
    notes: str
    created_at: datetime
    updated_at: datetime
