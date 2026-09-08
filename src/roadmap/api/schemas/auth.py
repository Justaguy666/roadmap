"""API schemas for authentication and user accounts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    """Request body for POST /api/v1/auth/register."""

    email: str = Field(min_length=3, max_length=255, description="User email address")
    password: str = Field(min_length=8, max_length=128, description="User password (min 8 chars)")


class UserLoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""

    email: str = Field(min_length=1, max_length=255, description="User email address")
    password: str = Field(min_length=1, max_length=128, description="User password")


class TokenResponse(BaseModel):
    """Response body containing bearer access token."""

    access_token: str = Field(description="Stateless signed JWT bearer token")
    token_type: str = Field(default="bearer", description="Token type")


class UserResponse(BaseModel):
    """Safe public representation of an authenticated user identity."""

    id: str
    email: str
    status: str
    created_at: datetime
