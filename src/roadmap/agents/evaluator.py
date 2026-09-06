"""Agent: RoadmapEvaluator.

Critiques and validates candidate roadmaps with structured evaluation outputs.
"""

from __future__ import annotations

from typing import Any

from roadmap.agents.prompts.evaluator import (
    ROADMAP_EVALUATOR_SYSTEM_PROMPT,
    build_roadmap_evaluation_prompt,
)
from roadmap.agents.schemas.evaluator import RoadmapEvaluationResult
from roadmap.application.ports.llm_provider import LLMMessage, LLMProvider
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.config.settings import settings
from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class RoadmapEvaluator:
    """Evaluates candidate roadmaps for structural, evidence, and pedagogical soundness."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        budget_manager: LLMBudgetManager | None = None,
    ) -> None:
        self.llm = llm_provider
        self.budget_manager = budget_manager

    def evaluate(
        self,
        target_role: str,
        target_goal: str,
        weekly_hours: float,
        deadline_weeks: int | float,
        candidate_roadmap_dict: dict[str, Any],
        market_summary_list: list[dict[str, Any]],
        deterministic_errors: list[str] | None = None,
    ) -> RoadmapEvaluationResult:
        """Run evaluator critique."""
        det_errors = deterministic_errors or []
        prompt = build_roadmap_evaluation_prompt(
            target_role=target_role,
            target_goal=target_goal,
            weekly_hours=weekly_hours,
            deadline_weeks=int(deadline_weeks),
            candidate_roadmap_json=candidate_roadmap_dict,
            market_summary_json=market_summary_list,
            deterministic_errors=det_errors,
        )

        messages = [
            LLMMessage(role="system", content=ROADMAP_EVALUATOR_SYSTEM_PROMPT),
            LLMMessage(role="user", content=prompt),
        ]

        logger.info(
            "Running RoadmapEvaluator agent",
            role=target_role,
            det_errors=len(det_errors),
        )

        reservation = None
        prov_name = getattr(self.llm, "provider_name", settings.llm_provider)
        mod_name = getattr(self.llm, "model_name", settings.llm_model or "default")
        if self.budget_manager:
            reservation = self.budget_manager.reserve(
                workflow=LLMWorkflow.EVALUATION,
                operation="candidate_evaluation",
                estimated_requests=1,
                provider=prov_name,
                model=mod_name,
            )

        try:
            result: RoadmapEvaluationResult = self.llm.complete(
                messages=messages,
                response_model=RoadmapEvaluationResult,
                temperature=0.1,
            )
            if self.budget_manager and reservation:
                self.budget_manager.commit(
                    reservation=reservation,
                    success=True,
                    actual_requests=1,
                )
            return result
        except Exception as exc:
            if self.budget_manager and reservation:
                fc = getattr(exc, "failure_category", FailureCategory.UNKNOWN_PROVIDER_ERROR)
                self.budget_manager.commit(
                    reservation=reservation,
                    success=False,
                    failure_category=fc,
                    actual_requests=1,
                    error_message=str(exc),
                )
            raise
