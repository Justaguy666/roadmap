"""Domain entity: ProgressRecord.

Tracks the user's progress on individual skills.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from roadmap.shared.ids import new_id


class ProgressStatus(str, Enum):
    """Lifecycle status of skill progress in MVP-5."""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"


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
    phase_id: str | None = Field(default=None, description="Optional phase ID")
    status: ProgressStatus = Field(
        default=ProgressStatus.NOT_STARTED,
        description="Current execution state of the skill",
    )

    completion_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="How far along the skill is (0–100%)",
    )
    planned_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Expected time commitment allocated for this skill",
    )
    actual_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Actual logged hours spent learning this skill",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Timestamp when progress was first recorded or status moved to IN_PROGRESS",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Set when completion_percentage reaches 100 or status is COMPLETED",
    )
    notes: str = Field(
        default="",
        max_length=1000,
        description="User notes about this progress update",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_complete(self) -> bool:
        return self.completion_percentage >= 100.0 or self.status == ProgressStatus.COMPLETED

    def mark_complete(self) -> None:
        self.completion_percentage = 100.0
        self.status = ProgressStatus.COMPLETED
        if self.started_at is None:
            self.started_at = datetime.now(UTC)
        self.completed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def update_progress(
        self,
        percentage: float,
        notes: str = "",
        actual_hours: float | None = None,
        status: ProgressStatus | None = None,
    ) -> None:
        self.completion_percentage = min(100.0, max(0.0, percentage))
        if actual_hours is not None and actual_hours >= 0:
            self.actual_hours = actual_hours
        if notes:
            self.notes = notes

        if status is not None:
            self.status = status
        elif self.is_complete:
            self.status = ProgressStatus.COMPLETED
        elif self.completion_percentage > 0:
            self.status = ProgressStatus.IN_PROGRESS

        now = datetime.now(UTC)
        if self.status in (ProgressStatus.IN_PROGRESS, ProgressStatus.COMPLETED) and self.started_at is None:
            self.started_at = now

        if self.is_complete and self.completed_at is None:
            self.completed_at = now
        elif not self.is_complete and self.status != ProgressStatus.COMPLETED:
            self.completed_at = None

        self.updated_at = now


