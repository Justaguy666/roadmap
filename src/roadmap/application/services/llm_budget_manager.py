"""
LLMBudgetManager: Orchestrates application-level LLM request budgets,
reservation tokens, provider failure classification, and cooldown tracking.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from roadmap.application.ports.llm_provider import (
    ApplicationBudgetExceededError,
    ProviderQuotaUnavailableError,
)
from roadmap.application.ports.llm_usage_repository import LLMUsageRepository
from roadmap.config.settings import settings
from roadmap.domain.entities.llm_budget import (
    BudgetAllocation,
    LLMProviderState,
    LLMQuotaStatus,
    LLMReservation,
    LLMUsageRecord,
)
from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class LLMBudgetManager:
    """
    Provider-agnostic budget and quota management service.
    Guarantees deterministic rejection before making upstream LLM requests.
    """

    def __init__(
        self,
        repository: LLMUsageRepository,
        daily_budget: int | None = None,
        workflow_budgets: dict[LLMWorkflow, int] | None = None,
        window_hours: int | None = None,
        cooldown_seconds: int | None = None,
    ) -> None:
        self.repository = repository
        self.daily_budget = daily_budget if daily_budget is not None else settings.daily_llm_budget
        self.window_hours = window_hours if window_hours is not None else settings.llm_budget_window_hours
        self.cooldown_seconds = (
            cooldown_seconds if cooldown_seconds is not None else settings.llm_provider_cooldown_seconds
        )

        wf_defaults = {
            LLMWorkflow.RESEARCH: settings.research_llm_budget,
            LLMWorkflow.GENERATION: settings.generation_llm_budget,
            LLMWorkflow.EVALUATION: settings.evaluation_llm_budget,
            LLMWorkflow.OTHER: max(1, self.daily_budget),
        }
        if workflow_budgets:
            wf_defaults.update(workflow_budgets)
        self.workflow_budgets = wf_defaults

        self._active_reservations: dict[str, LLMReservation] = {}
        self._lock = threading.Lock()

    def _get_window_start(self) -> datetime:
        return datetime.now(UTC) - timedelta(hours=self.window_hours)

    def check_provider_health(self, provider: str, model: str = "default") -> tuple[bool, str]:
        """
        Check if provider is available or in cooldown due to previous daily quota exhaustion.
        Returns (is_available, reason).
        If circuit-breaker cooldown has expired, allows a controlled re-probe attempt.
        """
        state = self.repository.get_provider_state(provider, model)
        if not state:
            return True, "Provider state clear"

        active_block_until = state.blocked_until or state.cooldown_until
        if active_block_until:
            now = datetime.now(UTC)
            # Ensure timezone awareness
            cd_until = active_block_until if active_block_until.tzinfo else active_block_until.replace(tzinfo=UTC)
            if now < cd_until:
                remaining_sec = int((cd_until - now).total_seconds())
                reason = (
                    f"Provider '{provider}' (model '{model}') is in cooldown for {remaining_sec}s "
                    f"(circuit-breaker active) after previous "
                    f"{state.last_failure_category.value if state.last_failure_category else 'daily quota'} failure."
                )
                return False, reason
            else:
                # Cooldown expired: allow a controlled re-probe
                logger.info(
                    "Allowing controlled re-probe for provider after circuit-breaker cooldown expired",
                    provider=provider,
                    model=model,
                    cooldown_expired_at=cd_until.isoformat(),
                )
                return True, "Re-probing provider after circuit-breaker expiration"

        return True, "Provider available"

    def check_budget(self, workflow: LLMWorkflow, requests: int = 1) -> tuple[bool, str]:
        """
        Check whether global and workflow-specific budgets have enough remaining capacity.
        Takes active uncommitted reservations into account.
        Returns (allowed, reason).
        """
        with self._lock:
            window_start = self._get_window_start()
            total_used = self.repository.count_requests_since(window_start)
            active_reserved_global = sum(r.reserved_requests for r in self._active_reservations.values())

            if total_used + active_reserved_global + requests > self.daily_budget:
                reason = (
                    f"Global LLM budget exhausted: used={total_used}, active_reserved={active_reserved_global}, "
                    f"requested={requests}, limit={self.daily_budget}."
                )
                return False, reason

            wf_limit = self.workflow_budgets.get(workflow, self.daily_budget)
            wf_used = self.repository.count_requests_since(window_start, workflow=workflow)
            active_reserved_wf = sum(
                r.reserved_requests for r in self._active_reservations.values() if r.workflow == workflow
            )

            if wf_used + active_reserved_wf + requests > wf_limit:
                reason = (
                    f"Workflow '{workflow.value}' LLM budget exhausted: used={wf_used}, "
                    f"active_reserved={active_reserved_wf}, requested={requests}, limit={wf_limit}."
                )
                return False, reason

            return True, "Budget available"

    def reserve(
        self,
        workflow: LLMWorkflow | str,
        operation: str = "completion",
        estimated_requests: int = 1,
        correlation_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> LLMReservation:
        """
        Reserve budget before calling an LLM.
        Raises ApplicationBudgetExceededError or ProviderQuotaUnavailableError if unavailable.
        """
        wf_enum = LLMWorkflow(workflow) if isinstance(workflow, str) else workflow

        # Check provider health first
        prov_name = provider or settings.llm_provider
        mod_name = model or settings.llm_model or "default"
        prov_avail, prov_reason = self.check_provider_health(prov_name, mod_name)
        if not prov_avail:
            logger.warning(
                "LLM provider request blocked by provider health cooldown",
                provider=prov_name,
                model=mod_name,
                reason=prov_reason,
            )
            raise ProviderQuotaUnavailableError(provider=prov_name, model=mod_name, message=prov_reason)

        allowed, reason = self.check_budget(wf_enum, estimated_requests)
        if not allowed:
            logger.warning(
                "LLM request blocked by application budget policy",
                workflow=wf_enum.value,
                operation=operation,
                reason=reason,
            )
            window_start = self._get_window_start()
            wf_used = self.repository.count_requests_since(window_start, workflow=wf_enum)
            wf_limit = self.workflow_budgets.get(wf_enum, self.daily_budget)
            raise ApplicationBudgetExceededError(
                workflow=wf_enum.value,
                allocated=wf_limit,
                used=wf_used,
                required=estimated_requests,
                message=reason,
            )

        reservation = LLMReservation(
            workflow=wf_enum,
            operation=operation,
            provider=prov_name,
            model=mod_name,
            reserved_requests=estimated_requests,
            correlation_id=correlation_id,
        )

        with self._lock:
            self._active_reservations[reservation.id] = reservation

        logger.info(
            "LLM budget reserved",
            reservation_id=reservation.id,
            workflow=wf_enum.value,
            operation=operation,
            provider=prov_name,
            model=mod_name,
            requests=estimated_requests,
        )
        return reservation

    def commit(
        self,
        reservation: LLMReservation,
        success: bool = True,
        failure_category: FailureCategory | None = None,
        provider: str | None = None,
        model: str | None = None,
        actual_requests: int | None = None,
        estimated_tokens: int = 0,
        error_message: str | None = None,
    ) -> LLMUsageRecord:
        """
        Commit a reservation upon operation completion or failure.
        Guarantees idempotency (cannot be double-committed).
        """
        with self._lock:
            if reservation.id in self._active_reservations:
                del self._active_reservations[reservation.id]

            if reservation.committed:
                logger.warning("Reservation already committed, ignoring duplicate commit", id=reservation.id)
                return LLMUsageRecord(id=reservation.id, workflow=reservation.workflow)

            reservation.committed = True

        # Use reservation's provider/model unless explicitly overridden
        commit_provider = provider or (reservation.provider if reservation.provider != "unknown" else settings.llm_provider)
        commit_model = model or (
            reservation.model
            if reservation.model != "unknown"
            else (settings.llm_model or (settings.gemini_model if commit_provider == "gemini" else (settings.openai_model if commit_provider == "openai" else "default")))
        )

        req_count = actual_requests if actual_requests is not None else reservation.reserved_requests
        record = LLMUsageRecord(
            workflow=reservation.workflow,
            provider=commit_provider,
            model=commit_model,
            operation=reservation.operation,
            success=success,
            failure_category=failure_category,
            reserved_requests=reservation.reserved_requests,
            actual_requests=req_count if (success or failure_category != FailureCategory.APPLICATION_BUDGET_EXCEEDED) else 0,
            estimated_tokens=estimated_tokens,
            correlation_id=reservation.correlation_id,
        )

        self.repository.save_usage(record)

        # If provider daily quota was exhausted, update provider state with cooldown
        if failure_category == FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED:
            self.record_provider_failure(
                provider=commit_provider,
                model=commit_model,
                failure_category=failure_category,
                cooldown_seconds=self.cooldown_seconds,
                error_message=error_message,
            )
        elif success:
            # If the request succeeded and there was an exhausted provider state, clear it
            existing_state = self.repository.get_provider_state(commit_provider, commit_model)
            if existing_state and (existing_state.quota_exhausted or existing_state.cooldown_until):
                logger.info(
                    "Re-probe succeeded, clearing provider cooldown and quota exhaustion",
                    provider=commit_provider,
                    model=commit_model,
                )
                self.clear_provider_cooldown(commit_provider, commit_model)

        logger.info(
            "LLM budget reservation committed",
            reservation_id=reservation.id,
            workflow=reservation.workflow.value,
            provider=commit_provider,
            model=commit_model,
            success=success,
            failure_category=failure_category.value if failure_category else None,
            actual_requests=record.actual_requests,
        )
        return record

    def release(self, reservation: LLMReservation) -> None:
        """Release reservation without recording usage (e.g. cancelled before call)."""
        with self._lock:
            if reservation.id in self._active_reservations:
                del self._active_reservations[reservation.id]
            reservation.committed = True
        logger.info("LLM budget reservation released", reservation_id=reservation.id)

    def record_provider_failure(
        self,
        provider: str,
        model: str,
        failure_category: FailureCategory,
        cooldown_seconds: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record a provider-level failure, placing it in cooldown if daily quota exhausted."""
        now = datetime.now(UTC)
        cd_until = None
        is_exhausted = (failure_category == FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED)
        if is_exhausted:
            secs = cooldown_seconds or self.cooldown_seconds
            cd_until = now + timedelta(seconds=secs)

        state = LLMProviderState(
            provider=provider,
            model=model,
            is_available=not is_exhausted,
            quota_exhausted=is_exhausted,
            last_failure_category=failure_category,
            last_failure_at=now,
            cooldown_until=cd_until,
            blocked_until=cd_until,
            error_message=error_message,
        )
        self.repository.save_provider_state(state)
        logger.warning(
            "Recorded provider health state",
            provider=provider,
            model=model,
            failure_category=failure_category.value,
            quota_exhausted=is_exhausted,
            blocked_until=cd_until.isoformat() if cd_until else None,
        )

    def clear_provider_cooldown(self, provider: str, model: str = "default") -> None:
        """Manually clear provider cooldown."""
        state = LLMProviderState(
            provider=provider,
            model=model,
            is_available=True,
            quota_exhausted=False,
            last_failure_category=None,
            last_failure_at=None,
            cooldown_until=None,
            blocked_until=None,
        )
        self.repository.save_provider_state(state)

    def get_quota_status(self) -> LLMQuotaStatus:
        """Produce comprehensive snapshot of application budgets and provider health."""
        window_start = self._get_window_start()
        with self._lock:
            total_used = self.repository.count_requests_since(window_start)
            active_reserved_global = sum(r.reserved_requests for r in self._active_reservations.values())
            global_alloc = BudgetAllocation(
                allocated=self.daily_budget,
                used=total_used,
                reserved=active_reserved_global,
            )

            wf_allocs: dict[LLMWorkflow, BudgetAllocation] = {}
            for wf in [LLMWorkflow.RESEARCH, LLMWorkflow.GENERATION, LLMWorkflow.EVALUATION]:
                limit = self.workflow_budgets.get(wf, self.daily_budget)
                used = self.repository.count_requests_since(window_start, workflow=wf)
                reserved = sum(r.reserved_requests for r in self._active_reservations.values() if r.workflow == wf)
                wf_allocs[wf] = BudgetAllocation(allocated=limit, used=used, reserved=reserved)

            provider_states = self.repository.list_provider_states()
            recent = self.repository.get_recent_usage(limit=10)

            return LLMQuotaStatus(
                timestamp=datetime.now(UTC),
                global_budget=global_alloc,
                workflow_budgets=wf_allocs,
                provider_states=provider_states,
                recent_usage=recent,
            )
