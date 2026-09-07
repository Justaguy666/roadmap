"""API schemas for Feedback endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreateRequest(BaseModel):
    """Request body for POST /api/v1/profiles/{id}/feedback."""

    skill_name: str = Field(min_length=1, max_length=200)
    difficulty: int = Field(ge=1, le=5, description="Perceived difficulty 1 (easy) to 5 (very hard)")
    confidence: int = Field(ge=1, le=5, description="Confidence level 1 (low) to 5 (high)")
    satisfaction: int = Field(ge=1, le=5, description="Satisfaction with resources 1 (low) to 5 (high)")
    blocked_reason: str = Field(default="", max_length=500, description="Why you are blocked, if any")
    free_text: str = Field(default="", max_length=2000, description="Free-form qualitative feedback")


class FeedbackResponse(BaseModel):
    """Response body for feedback endpoints."""

    id: str
    profile_id: str
    roadmap_id: str
    skill_name: str
    difficulty: int
    confidence: int
    satisfaction: int
    blocked_reason: str
    free_text: str
    created_at: datetime
