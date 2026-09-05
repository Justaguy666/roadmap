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
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class RoadmapEvaluator:
    """Evaluates candidate roadmaps for structural, evidence, and pedagogical soundness."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm = llm_provider

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

        result: RoadmapEvaluationResult = self.llm.complete(
            messages=messages,
            response_model=RoadmapEvaluationResult,
            temperature=0.1,
        )

        return result
