"""Domain entities: DeviationReport & RoadmapAdaptation.

Defines deterministic deviation metrics and immutable roadmap adaptation records.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from roadmap.shared.ids import new_id


class DeviationStatus(str, Enum):
    """Classification of learning progress deviation."""

    ON_TRACK = "ON_TRACK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DeviationReport(BaseModel):
    """
    Deterministic deviation analysis comparing planned vs. actual progress.
    """

    roadmap_id: str
    profile_id: str
    status: DeviationStatus = DeviationStatus.ON_TRACK

    # Metric comparisons
    total_planned_hours: float = 0.0
    total_actual_hours: float = 0.0
    expected_completion_percentage: float = 0.0
    actual_completion_percentage: float = 0.0

    # Calculated ratios
    velocity_ratio: float = 1.0  # planned_hours_done / actual_hours_spent
    progress_deviation: float = 0.0  # expected_pct - actual_pct

    # Signals
    blocked_skills: list[str] = Field(default_factory=list)
    behind_skills: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def requires_adaptation(self) -> bool:
        """True if progress deviation is critical or blocked skills require restructuring."""
        return self.status == DeviationStatus.CRITICAL or len(self.blocked_skills) > 0


class RoadmapAdaptation(BaseModel):
    """
    Audit record linking an old roadmap version to its adapted successor version.
    """

    id: str = Field(default_factory=new_id)
    profile_id: str
    previous_roadmap_id: str
    new_roadmap_id: str
    previous_version: int
    new_version: int

    trigger_reason: str = Field(
        description="Trigger rationale (e.g., 'CRITICAL deviation detected', 'User requested replanning')",
    )
    deviation_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of deviation metrics that triggered the change",
    )
    user_feedback_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated user ratings and blockers informing the adaptation",
    )
    changes_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of modifications applied (e.g. durations changed, skills reordered/added)",
    )
    accepted: bool = Field(
        default=True,
        description="Whether user confirmed and accepted the adapted roadmap",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
