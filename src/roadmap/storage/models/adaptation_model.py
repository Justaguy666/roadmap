"""ORM model: RoadmapAdaptation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from roadmap.storage.models.base import Base


class RoadmapAdaptationModel(Base):
    __tablename__ = "roadmap_adaptations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    previous_roadmap_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False
    )
    new_roadmap_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False
    )
    previous_version: Mapped[int] = mapped_column(Integer, nullable=False)
    new_version: Mapped[int] = mapped_column(Integer, nullable=False)

    trigger_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    deviation_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    user_feedback_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    changes_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    @property
    def deviation_summary(self) -> dict[str, Any]:
        return json.loads(self.deviation_summary_json)

    @deviation_summary.setter
    def deviation_summary(self, val: dict[str, Any]) -> None:
        self.deviation_summary_json = json.dumps(val)

    @property
    def user_feedback_summary(self) -> dict[str, Any]:
        return json.loads(self.user_feedback_summary_json)

    @user_feedback_summary.setter
    def user_feedback_summary(self, val: dict[str, Any]) -> None:
        self.user_feedback_summary_json = json.dumps(val)

    @property
    def changes_summary(self) -> dict[str, Any]:
        return json.loads(self.changes_summary_json)

    @changes_summary.setter
    def changes_summary(self, val: dict[str, Any]) -> None:
        self.changes_summary_json = json.dumps(val)
