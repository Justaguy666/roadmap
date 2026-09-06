"""
Application use case: AnalyzeGoalUseCase.

Analyzes a user's target career/learning goal using the LLMProvider
and produces a structured competency breakdown.
"""

from __future__ import annotations

import time

from roadmap.agents.prompts.goal_analysis import (
    GOAL_ANALYSIS_SYSTEM_PROMPT,
    build_goal_analysis_user_prompt,
)
from roadmap.agents.schemas.goal_analysis import GoalAnalysisResult
from roadmap.application.ports.llm_provider import LLMMessage, LLMProvider
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.config.settings import settings
from roadmap.domain.entities.goal import Competency, Goal
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class AnalyzeGoalUseCase:
    """
    Orchestrates the analysis of a UserProfile's target goal.
    Calls LLMProvider to infer the structured competency model.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        budget_manager: LLMBudgetManager | None = None,
    ) -> None:
        self.llm_provider = llm_provider
        self.budget_manager = budget_manager

    def execute(self, profile: UserProfile) -> GoalAnalysisResult:
        """
        Analyze the user's target goal and return the validated GoalAnalysisResult.
        """
        start_time = time.perf_counter()
        logger.info(
            "Starting goal analysis",
            profile_id=profile.id,
            target_goal=profile.target_goal,
        )

        user_content = build_goal_analysis_user_prompt(profile)
        messages = [
            LLMMessage.system(GOAL_ANALYSIS_SYSTEM_PROMPT),
            LLMMessage.user(user_content),
        ]

        reservation = None
        prov_name = getattr(self.llm_provider, "provider_name", settings.llm_provider)
        mod_name = getattr(self.llm_provider, "model_name", settings.llm_model or "default")
        if self.budget_manager:
            reservation = self.budget_manager.reserve(
                workflow=LLMWorkflow.GENERATION,
                operation="goal_analysis",
                estimated_requests=1,
                correlation_id=profile.id,
                provider=prov_name,
                model=mod_name,
            )

        try:
            result: GoalAnalysisResult = self.llm_provider.complete(
                messages=messages,
                response_model=GoalAnalysisResult,
            )
            if self.budget_manager and reservation:
                self.budget_manager.commit(
                    reservation=reservation,
                    success=True,
                    actual_requests=1,
                )
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

        elapsed = time.perf_counter() - start_time
        logger.info(
            "Goal analysis completed",
            profile_id=profile.id,
            target_role=result.target_role,
            num_competencies=len(result.competencies),
            num_required_skills=len(result.required_skills),
            confidence=result.confidence,
            duration_seconds=round(elapsed, 2),
        )

        return result

    def to_domain_goal(self, profile: UserProfile, analysis: GoalAnalysisResult) -> Goal:
        """
        Convert structured GoalAnalysisResult into the domain Goal entity.
        """
        domain_competencies = [
            Competency(
                id=new_id(),
                name=c.name,
                description=c.description,
                importance_score=c.importance_score,
                skill_names=c.skill_names,
            )
            for c in analysis.competencies
        ]

        goal = Goal(
            id=new_id(),
            profile_id=profile.id,
            raw_goal=profile.target_goal,
            target_role=analysis.target_role,
            context=f"Interpreted Goal: {analysis.interpreted_goal}",
            competencies=domain_competencies,
            required_skill_names=[s.name for s in analysis.required_skills],
            assumptions=analysis.assumptions,
        )
        goal.mark_analyzed()
        return goal
