"""SQLAlchemy repository implementation for LLM usage tracking and provider state persistence."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from roadmap.application.ports.llm_usage_repository import LLMUsageRepository
from roadmap.domain.entities.llm_budget import LLMProviderState, LLMUsageRecord
from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow
from roadmap.storage.models.llm_usage_model import LLMProviderStateModel, LLMUsageRecordModel


class SqliteLLMUsageRepository(LLMUsageRepository):
    """SQLite repository for LLMUsageRecord and LLMProviderState."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_usage(self, record: LLMUsageRecord) -> None:
        m = LLMUsageRecordModel(
            id=record.id,
            timestamp=record.timestamp,
            workflow=record.workflow.value if isinstance(record.workflow, LLMWorkflow) else str(record.workflow),
            provider=record.provider,
            model=record.model,
            operation=record.operation,
            success=record.success,
            failure_category=record.failure_category.value if record.failure_category else None,
            reserved_requests=record.reserved_requests,
            actual_requests=record.actual_requests,
            estimated_tokens=record.estimated_tokens,
            correlation_id=record.correlation_id,
        )
        self._session.add(m)
        self._session.flush()

    def get_recent_usage(self, limit: int = 50) -> list[LLMUsageRecord]:
        rows = (
            self._session.query(LLMUsageRecordModel)
            .order_by(LLMUsageRecordModel.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [self._to_usage_entity(r) for r in rows]

    def count_requests_since(
        self,
        since: datetime,
        workflow: LLMWorkflow | None = None,
        only_successful: bool = False,
    ) -> int:
        q = self._session.query(func.sum(LLMUsageRecordModel.actual_requests)).filter(
            LLMUsageRecordModel.timestamp >= since
        )
        if workflow:
            q = q.filter(LLMUsageRecordModel.workflow == workflow.value)
        if only_successful:
            q = q.filter(LLMUsageRecordModel.success.is_(True))

        result = q.scalar()
        return int(result or 0)

    def save_provider_state(self, state: LLMProviderState) -> None:
        composite_id = f"{state.provider}:{state.model}".lower()
        existing = self._session.get(LLMProviderStateModel, composite_id)
        if existing:
            existing.is_available = state.is_available
            existing.last_failure_category = (
                state.last_failure_category.value if state.last_failure_category else None
            )
            existing.last_failure_at = state.last_failure_at
            existing.cooldown_until = state.cooldown_until
            existing.error_message = state.error_message
            existing.updated_at = datetime.now(UTC)
        else:
            m = LLMProviderStateModel(
                id=composite_id,
                provider=state.provider,
                model=state.model,
                is_available=state.is_available,
                last_failure_category=(
                    state.last_failure_category.value if state.last_failure_category else None
                ),
                last_failure_at=state.last_failure_at,
                cooldown_until=state.cooldown_until,
                error_message=state.error_message,
                updated_at=datetime.now(UTC),
            )
            self._session.add(m)
        self._session.flush()

    def get_provider_state(self, provider: str, model: str = "default") -> LLMProviderState | None:
        composite_id = f"{provider}:{model}".lower()
        m = self._session.get(LLMProviderStateModel, composite_id)
        if not m:
            return None
        return self._to_provider_state_entity(m)

    def list_provider_states(self) -> list[LLMProviderState]:
        rows = self._session.query(LLMProviderStateModel).all()
        return [self._to_provider_state_entity(r) for r in rows]

    @staticmethod
    def _to_usage_entity(m: LLMUsageRecordModel) -> LLMUsageRecord:
        wf = LLMWorkflow.OTHER
        with contextlib.suppress(ValueError):
            wf = LLMWorkflow(m.workflow)

        fc = None
        if m.failure_category:
            with contextlib.suppress(ValueError):
                fc = FailureCategory(m.failure_category)

        return LLMUsageRecord(
            id=m.id,
            timestamp=m.timestamp,
            workflow=wf,
            provider=m.provider,
            model=m.model,
            operation=m.operation,
            success=m.success,
            failure_category=fc,
            reserved_requests=m.reserved_requests,
            actual_requests=m.actual_requests,
            estimated_tokens=m.estimated_tokens,
            correlation_id=m.correlation_id,
        )

    @staticmethod
    def _to_provider_state_entity(m: LLMProviderStateModel) -> LLMProviderState:
        fc = None
        if m.last_failure_category:
            with contextlib.suppress(ValueError):
                fc = FailureCategory(m.last_failure_category)

        return LLMProviderState(
            provider=m.provider,
            model=m.model,
            is_available=m.is_available,
            last_failure_category=fc,
            last_failure_at=m.last_failure_at,
            cooldown_until=m.cooldown_until,
            error_message=m.error_message,
        )
