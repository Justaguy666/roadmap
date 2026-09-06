"""
Port interface for persisting and retrieving LLM usage records and provider health states.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from roadmap.domain.entities.llm_budget import LLMProviderState, LLMUsageRecord
from roadmap.domain.value_objects.enums import LLMWorkflow


class LLMUsageRepository(Protocol):
    """Abstract port for LLM usage and provider state persistence."""

    def save_usage(self, record: LLMUsageRecord) -> None:
        """Persist an LLM usage/attempt record."""
        ...

    def get_recent_usage(self, limit: int = 50) -> list[LLMUsageRecord]:
        """Retrieve recent usage records across all workflows."""
        ...

    def count_requests_since(
        self,
        since: datetime,
        workflow: LLMWorkflow | None = None,
        only_successful: bool = False,
    ) -> int:
        """
        Count requests made since a specific datetime.
        If workflow is specified, counts requests for that workflow.
        """
        ...

    def save_provider_state(self, state: LLMProviderState) -> None:
        """Persist or update provider health / cooldown state."""
        ...

    def get_provider_state(self, provider: str, model: str = "default") -> LLMProviderState | None:
        """Retrieve health / cooldown state for a specific provider and model."""
        ...

    def list_provider_states(self) -> list[LLMProviderState]:
        """List all tracked provider states."""
        ...
