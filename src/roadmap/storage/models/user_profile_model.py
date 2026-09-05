"""ORM model: UserProfile."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from roadmap.storage.models.base import Base


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_goal: Mapped[str] = mapped_column(Text, nullable=False)
    target_role: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    current_level: Mapped[str] = mapped_column(String(20), nullable=False, default="missing")

    # JSON-serialized lists
    current_skills_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    programming_languages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    previous_experience: Mapped[str] = mapped_column(Text, nullable=False, default="")
    completed_projects_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preferred_technologies_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preferred_industry: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    target_markets_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    learning_preferences_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    budget: Mapped[str] = mapped_column(String(20), nullable=False, default="any")
    constraints_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    study_hours_per_day: Mapped[float] = mapped_column(nullable=False, default=2.0)
    deadline_months: Mapped[int] = mapped_column(nullable=False, default=12)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    # Helper properties for JSON serialization
    @property
    def current_skills(self) -> list[str]:
        return json.loads(self.current_skills_json)

    @current_skills.setter
    def current_skills(self, value: list[str]) -> None:
        self.current_skills_json = json.dumps(value)

    @property
    def programming_languages(self) -> list[str]:
        return json.loads(self.programming_languages_json)

    @programming_languages.setter
    def programming_languages(self, value: list[str]) -> None:
        self.programming_languages_json = json.dumps(value)

    @property
    def completed_projects(self) -> list[str]:
        return json.loads(self.completed_projects_json)

    @completed_projects.setter
    def completed_projects(self, value: list[str]) -> None:
        self.completed_projects_json = json.dumps(value)

    @property
    def preferred_technologies(self) -> list[str]:
        return json.loads(self.preferred_technologies_json)

    @preferred_technologies.setter
    def preferred_technologies(self, value: list[str]) -> None:
        self.preferred_technologies_json = json.dumps(value)

    @property
    def target_markets(self) -> list[str]:
        return json.loads(self.target_markets_json)

    @target_markets.setter
    def target_markets(self, value: list[str]) -> None:
        self.target_markets_json = json.dumps(value)

    @property
    def learning_preferences(self) -> list[str]:
        return json.loads(self.learning_preferences_json)

    @learning_preferences.setter
    def learning_preferences(self, value: list[str]) -> None:
        self.learning_preferences_json = json.dumps(value)

    @property
    def constraints(self) -> list[str]:
        return json.loads(self.constraints_json)

    @constraints.setter
    def constraints(self, value: list[str]) -> None:
        self.constraints_json = json.dumps(value)

