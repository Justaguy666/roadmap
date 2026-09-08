"""
Shared API response/error schemas for RoadmapAI.

All error responses follow the structure:
  {"error": {"code": "ERROR_CODE", "message": "Human-readable message"}}

This ensures a stable, predictable contract for API consumers.

Note: Authentication is not yet implemented (MVP-7.3 concern).
Note: All endpoints are currently unauthenticated.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detail block inside an error response."""

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error description")


class ErrorResponse(BaseModel):
    """Standard API error response envelope."""

    error: ErrorDetail


# Canonical error codes used across all routers
class ErrorCode:
    # Profile
    PROFILE_NOT_FOUND = "PROFILE_NOT_FOUND"
    PROFILE_ALREADY_EXISTS = "PROFILE_ALREADY_EXISTS"

    # Roadmap
    ROADMAP_NOT_FOUND = "ROADMAP_NOT_FOUND"
    ROADMAP_VALIDATION_FAILED = "ROADMAP_VALIDATION_FAILED"

    # Skill
    SKILL_NOT_FOUND = "SKILL_NOT_FOUND"

    # Progress / Feedback
    INVALID_PROGRESS = "INVALID_PROGRESS"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Budget
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"

    # Provider
    PROVIDER_ERROR = "PROVIDER_ERROR"

    # Auth & Identity (MVP-7.3)
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    FORBIDDEN = "FORBIDDEN"
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"

    # General
    BAD_REQUEST = "BAD_REQUEST"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
