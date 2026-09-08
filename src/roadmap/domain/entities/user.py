"""Domain entity: User.

Represents authentication identity and credentials.
Pure Python / Pydantic — no database or external library imports.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from roadmap.shared.ids import new_id

LEGACY_LOCAL_USER_ID = "legacy-local-user-000000000000"
LEGACY_LOCAL_USER_EMAIL = "local@roadmap.ai"


class User(BaseModel):
    """User entity representing an authentication account."""

    id: str = Field(default_factory=new_id)
    email: str = Field(min_length=3, max_length=255)
    password_hash: str = Field(min_length=1, max_length=255)
    status: str = Field(default="active", max_length=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)
