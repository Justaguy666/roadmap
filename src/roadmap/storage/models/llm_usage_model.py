"SQLAlchemy ORM models for LLM usage records and provider health states."

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from roadmap.storage.models.base import Base


class LLMUsageRecordModel(Base):
    """Stores individual LLM request events and attempts."""

    __tablename__ = "llm_usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    workflow: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failure_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reserved_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    actual_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class LLMProviderStateModel(Base):
    """Stores health, last error, and cooldown status for an LLM provider and model."""

    __tablename__ = "llm_provider_states"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # composite provider:model
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_failure_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
