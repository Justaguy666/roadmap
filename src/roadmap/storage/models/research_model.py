"""ORM models for Research: Source, Evidence, ResearchRun, Recommendation."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from roadmap.storage.models.base import Base


class ResearchRunModel(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    target_market: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queries_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    errors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def queries(self) -> list[str]:
        return json.loads(self.queries_json)

    @queries.setter
    def queries(self, val: list[str]) -> None:
        self.queries_json = json.dumps(val)

    @property
    def errors(self) -> list[str]:
        return json.loads(self.errors_json)

    @errors.setter
    def errors(self, val: list[str]) -> None:
        self.errors_json = json.dumps(val)


class EvidenceModel(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    extracted_claim: Mapped[str] = mapped_column(Text, nullable=False)
    relevance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    associated_skill_names_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    @property
    def associated_skill_names(self) -> list[str]:
        return json.loads(self.associated_skill_names_json)

    @associated_skill_names.setter
    def associated_skill_names(self, val: list[str]) -> None:
        self.associated_skill_names_json = json.dumps(val)


class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(36), nullable=False)
    roadmap_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    decision_factors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    @property
    def decision_factors(self) -> list[str]:
        return json.loads(self.decision_factors_json)

    @decision_factors.setter
    def decision_factors(self, val: list[str]) -> None:
        self.decision_factors_json = json.dumps(val)

    @property
    def evidence_ids(self) -> list[str]:
        return json.loads(self.evidence_ids_json)

    @evidence_ids.setter
    def evidence_ids(self, val: list[str]) -> None:
        self.evidence_ids_json = json.dumps(val)
