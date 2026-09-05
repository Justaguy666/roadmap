"""ORM models: Roadmap, RoadmapPhase, Milestone, LearningResource, Project."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from roadmap.storage.models.base import Base


class RoadmapModel(Base):
    __tablename__ = "roadmaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    total_estimated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    skipped_skill_names_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    research_run_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    @property
    def assumptions(self) -> list[str]:
        return json.loads(self.assumptions_json)

    @assumptions.setter
    def assumptions(self, value: list[str]) -> None:
        self.assumptions_json = json.dumps(value)

    @property
    def skipped_skill_names(self) -> list[str]:
        return json.loads(self.skipped_skill_names_json)

    @skipped_skill_names.setter
    def skipped_skill_names(self, value: list[str]) -> None:
        self.skipped_skill_names_json = json.dumps(value)


class RoadmapPhaseModel(Base):
    __tablename__ = "roadmap_phases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    roadmap_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False
    )
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    estimated_weeks: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    # Serialized skill IDs for this phase
    skill_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")


class MilestoneModel(Base):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phase_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roadmap_phases.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    exit_criteria_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    estimated_weeks: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_achieved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def exit_criteria(self) -> list[str]:
        return json.loads(self.exit_criteria_json)

    @exit_criteria.setter
    def exit_criteria(self, value: list[str]) -> None:
        self.exit_criteria_json = json.dumps(value)


class LearningResourceModel(Base):
    __tablename__ = "learning_resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phase_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roadmap_phases.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False, default="course")
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="familiar")
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    freshness_year: Mapped[int] = mapped_column(Integer, nullable=False, default=2024)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    associated_skill_names_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phase_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roadmap_phases.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_skill_names_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="familiar")
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False, default="")
    portfolio_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

