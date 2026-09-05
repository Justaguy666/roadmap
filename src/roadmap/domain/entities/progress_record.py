"""Domain entity: ProgressRecord.

Tracks the user's progress on individual skills.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from roadmap.shared.ids import new_id


class ProgressRecord(BaseModel):
    """
    A progress entry for a specific skill.

    Multiple records may exist per skill (one per update).
    The latest record is the current state.
    """

    id: str = Field(default_factory=new_id)
    profile_id: str = Field(description="Owning profile ID")
    skill_id: str = Field(description="Skill being tracked")
    skill_name: str = Field(
        default="",
        description="Denormalized skill name for easy display",
    )

    completion_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="How far along the skill is (0–100%)",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Set when completion_percentage reaches 100",
    )
    notes: str = Field(
        default="",
        max_length=1000,
        description="User notes about this progress update",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_complete(self) -> bool:
        return self.completion_percentage >= 100.0

    def mark_complete(self) -> None:
        self.completion_percentage = 100.0
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def update_progress(self, percentage: float, notes: str = "") -> None:
        self.completion_percentage = min(100.0, max(0.0, percentage))
        if notes:
            self.notes = notes
        if self.is_complete and self.completed_at is None:
            self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

