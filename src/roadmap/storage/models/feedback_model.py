"""ORM model: LearningFeedback."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from roadmap.storage.models.base import Base


class LearningFeedbackModel(Base):
    __tablename__ = "learning_feedbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    roadmap_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    phase_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    satisfaction: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    blocked_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    free_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    @property
    def metadata_dict(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)

    @metadata_dict.setter
    def metadata_dict(self, val: dict[str, Any]) -> None:
        self.metadata_json = json.dumps(val)
