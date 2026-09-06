"""Unit tests for LLMBudgetManager."""

from datetime import datetime

import pytest

from roadmap.application.ports.llm_provider import (
    ApplicationBudgetExceededError,
    ProviderQuotaUnavailableError,
)
from roadmap.application.ports.llm_usage_repository import LLMUsageRepository
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.domain.entities.llm_budget import LLMProviderState, LLMUsageRecord
from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow


class InMemoryLLMUsageRepository(LLMUsageRepository):
    def __init__(self) -> None:
        self.records: list[LLMUsageRecord] = []
        self.states: dict[str, LLMProviderState] = {}

    def save_usage(self, record: LLMUsageRecord) -> None:
        self.records.append(record)

    def get_recent_usage(self, limit: int = 50) -> list[LLMUsageRecord]:
        return sorted(self.records, key=lambda r: r.timestamp, reverse=True)[:limit]

    def count_requests_since(
        self,
        since: datetime,
        workflow: LLMWorkflow | None = None,
        only_successful: bool = False,
    ) -> int:
        count = 0
        for r in self.records:
            if r.timestamp >= since:
                if workflow and r.workflow != workflow:
                    continue
                if only_successful and not r.success:
                    continue
                count += r.actual_requests
        return count

    def save_provider_state(self, state: LLMProviderState) -> None:
        key = f"{state.provider}:{state.model}".lower()
        self.states[key] = state

    def get_provider_state(self, provider: str, model: str = "default") -> LLMProviderState | None:
        return self.states.get(f"{provider}:{model}".lower())

    def list_provider_states(self) -> list[LLMProviderState]:
        return list(self.states.values())


def test_budget_reservation_and_commit() -> None:
    repo = InMemoryLLMUsageRepository()
    mgr = LLMBudgetManager(
        repository=repo,
        daily_budget=5,
        workflow_budgets={LLMWorkflow.GENERATION: 3},
    )

    # Reserve 1 request for generation
    res = mgr.reserve(LLMWorkflow.GENERATION, operation="generate_roadmap", estimated_requests=1)
    assert res.workflow == LLMWorkflow.GENERATION
    assert res.reserved_requests == 1
    assert not res.committed

    # Active pending reservations reduce available capacity
    allowed, reason = mgr.check_budget(LLMWorkflow.GENERATION, requests=3)
    assert not allowed  # 1 pending + 3 > 3

    # Commit reservation
    record = mgr.commit(res, success=True, provider="gemini", model="gemini-3.7-flash", actual_requests=1)
    assert record.success
    assert res.committed
    assert len(repo.records) == 1
    assert repo.records[0].actual_requests == 1

    # Now repo has 1 used, 0 pending. Checking 2 requests should be allowed
    allowed, _ = mgr.check_budget(LLMWorkflow.GENERATION, requests=2)
    assert allowed


def test_workflow_budget_exhaustion_raises_error() -> None:
    repo = InMemoryLLMUsageRepository()
    mgr = LLMBudgetManager(
        repository=repo,
        daily_budget=10,
        workflow_budgets={LLMWorkflow.RESEARCH: 2},
    )

    res1 = mgr.reserve(LLMWorkflow.RESEARCH, operation="batch_extract", estimated_requests=2)
    mgr.commit(res1, success=True, actual_requests=2)

    with pytest.raises(ApplicationBudgetExceededError) as exc_info:
        mgr.reserve(LLMWorkflow.RESEARCH, operation="batch_extract", estimated_requests=1)

    assert "Workflow 'research' LLM budget exhausted" in str(exc_info.value)
    assert exc_info.value.workflow == "research"
    assert exc_info.value.allocated == 2
    assert exc_info.value.used == 2


def test_global_budget_exhaustion_raises_error() -> None:
    repo = InMemoryLLMUsageRepository()
    mgr = LLMBudgetManager(
        repository=repo,
        daily_budget=3,
        workflow_budgets={
            LLMWorkflow.RESEARCH: 2,
            LLMWorkflow.GENERATION: 2,
        },
    )

    # Use 2 for research
    r1 = mgr.reserve(LLMWorkflow.RESEARCH, estimated_requests=2)
    mgr.commit(r1, success=True, actual_requests=2)

    # Use 1 for generation
    r2 = mgr.reserve(LLMWorkflow.GENERATION, estimated_requests=1)
    mgr.commit(r2, success=True, actual_requests=1)

    # Total used is 3 / 3 daily budget. Any new reservation should fail globally
    with pytest.raises(ApplicationBudgetExceededError) as exc_info:
        mgr.reserve(LLMWorkflow.GENERATION, estimated_requests=1)

    assert "Global LLM budget exhausted" in str(exc_info.value)


def test_provider_cooldown_blocks_requests() -> None:
    repo = InMemoryLLMUsageRepository()
    mgr = LLMBudgetManager(
        repository=repo,
        daily_budget=10,
        cooldown_seconds=3600,
    )

    res = mgr.reserve(LLMWorkflow.GENERATION, provider="gemini", model="gemini-3.7-flash")
    # Commit with daily quota failure
    mgr.commit(
        res,
        success=False,
        failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED,
        provider="gemini",
        model="gemini-3.7-flash",
        error_message="ResourceExhausted: 429",
    )

    # Check health
    avail, reason = mgr.check_provider_health("gemini", "gemini-3.7-flash")
    assert not avail
    assert "in cooldown" in reason

    # Attempting another reservation must immediately raise ProviderQuotaUnavailableError
    with pytest.raises(ProviderQuotaUnavailableError) as exc_info:
        mgr.reserve(LLMWorkflow.GENERATION, provider="gemini", model="gemini-3.7-flash")

    assert "in cooldown" in str(exc_info.value)


def test_reservation_release() -> None:
    repo = InMemoryLLMUsageRepository()
    mgr = LLMBudgetManager(repository=repo, daily_budget=2)

    res = mgr.reserve(LLMWorkflow.OTHER, estimated_requests=2)
    # Check that capacity is occupied
    allowed, _ = mgr.check_budget(LLMWorkflow.OTHER, requests=1)
    assert not allowed

    # Release reservation without using LLM
    mgr.release(res)
    assert res.committed
    assert len(repo.records) == 0

    # Capacity freed
    allowed, _ = mgr.check_budget(LLMWorkflow.OTHER, requests=2)
    assert allowed
