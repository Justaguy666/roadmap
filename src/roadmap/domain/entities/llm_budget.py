"""
Domain entities for LLM budget, reservation, and usage accounting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow
from roadmap.shared.ids import new_id


@dataclass
class LLMUsageRecord:
    """Historical record of an attempted or completed LLM request."""

    id: str = field(default_factory=new_id)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    workflow: LLMWorkflow = LLMWorkflow.OTHER
    provider: str = "unknown"
    model: str = "unknown"
    operation: str = "completion"
    success: bool = True
    failure_category: FailureCategory | None = None
    reserved_requests: int = 1
    actual_requests: int = 1
    estimated_tokens: int = 0
    correlation_id: str | None = None


@dataclass
class LLMReservation:
    """Token representing reserved budget before executing an LLM request."""

    id: str = field(default_factory=new_id)
    workflow: LLMWorkflow = LLMWorkflow.OTHER
    operation: str = "completion"
    reserved_requests: int = 1
    correlation_id: str | None = None
    committed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class LLMProviderState:
    """Provider health and cooldown tracking."""

    provider: str
    model: str = "default"
    is_available: bool = True
    last_failure_category: FailureCategory | None = None
    last_failure_at: datetime | None = None
    cooldown_until: datetime | None = None
    error_message: str | None = None


@dataclass
class BudgetAllocation:
    """Budget numbers for a specific scope."""

    allocated: int
    used: int
    reserved: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.allocated - self.used - self.reserved)


@dataclass
class LLMQuotaStatus:
    """Aggregate snapshot of application budgets and provider health."""

    timestamp: datetime
    global_budget: BudgetAllocation
    workflow_budgets: dict[LLMWorkflow, BudgetAllocation]
    provider_states: list[LLMProviderState]
    recent_usage: list[LLMUsageRecord] = field(default_factory=list)
