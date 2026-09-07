"""Agent: AdaptationAgent.

Analyzes learner progress records, qualitative feedback, and deviation reports,
and generates structured adaptation proposals to adjust pacing, restructure phases,
or introduce remedial support skills without disrupting mastered competencies.
"""

from __future__ import annotations

import json

from roadmap.agents.schemas.adaptation import AdaptationProposal
from roadmap.application.ports.llm_provider import LLMMessage, LLMProvider
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.domain.entities.adaptation import DeviationReport
from roadmap.domain.entities.feedback import LearningFeedback
from roadmap.domain.entities.progress_record import ProgressRecord
from roadmap.domain.entities.roadmap import Roadmap
from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert Adaptive Curriculum & Learning Progression Agent.
Your role is to analyze a learner's recorded progress, qualitative feedback, and schedule deviations,
and propose targeted, minimal, and non-destructive adjustments to their learning roadmap.

GUIDELINES:
1. PRESERVE MASTERED SKILLS: Never remove, un-complete, or demote skills that the user has already completed.
2. TARGETED MINIMAL INTERVENTION: Prefer adjusting hours, extending phase timelines, or adding focused support skills rather than rewriting the entire roadmap.
3. RESPECT PREREQUISITES: If introducing remedial skills or moving skills between phases, always respect prerequisite dependencies (DAG order).
4. EMPATHY & CLARITY: Provide clear rationales for every adjustment explaining why it addresses the learner's velocity, difficulty, or blocker.
5. REALISTIC PACING: If actual hours significantly exceed planned hours, increase duration estimates to prevent perpetual schedule slip.
"""


class AdaptationAgent:
    def __init__(
        self,
        llm_provider: LLMProvider,
        budget_manager: LLMBudgetManager | None = None,
    ) -> None:
        self.llm_provider = llm_provider
        self.budget_manager = budget_manager

    def propose_adaptation(
        self,
        roadmap: Roadmap,
        progress_records: list[ProgressRecord],
        feedback_records: list[LearningFeedback],
        deviation_report: DeviationReport,
    ) -> AdaptationProposal:
        """
        Generate a structured adaptation proposal using the LLM provider,
        governed under the ADAPTATION workflow budget.
        """
        # Context construction
        roadmap_summary = {
            "title": roadmap.title,
            "version": roadmap.version,
            "total_weeks": roadmap.total_weeks,
            "total_estimated_hours": roadmap.total_estimated_hours,
            "phases": [
                {
                    "phase_number": p.phase_number,
                    "name": p.name,
                    "estimated_weeks": p.estimated_weeks,
                    "is_completed": p.is_completed,
                    "skills": [
                        {
                            "name": s.name,
                            "estimated_hours": s.estimated_hours,
                            "status": s.status.value,
                            "prerequisites": s.prerequisite_names,
                        }
                        for s in p.skills
                    ],
                }
                for p in roadmap.phases
            ],
        }

        progress_summary = [
            {
                "skill_name": r.skill_name,
                "status": r.status.value,
                "completion_percentage": r.completion_percentage,
                "planned_hours": r.planned_hours,
                "actual_hours": r.actual_hours,
                "notes": r.notes,
            }
            for r in progress_records
        ]

        feedback_summary = [
            {
                "skill_name": f.skill_name,
                "difficulty": f.difficulty,
                "confidence": f.confidence,
                "satisfaction": f.satisfaction,
                "blocked_reason": f.blocked_reason,
                "notes": f.free_text,
            }
            for f in feedback_records
        ]

        deviation_summary = {
            "status": deviation_report.status.value,
            "velocity_ratio": deviation_report.velocity_ratio,
            "progress_deviation_pct": int(deviation_report.progress_deviation * 100),
            "blocked_skills": deviation_report.blocked_skills,
            "issues": deviation_report.issues,
            "recommendations": deviation_report.recommendations,
        }

        user_content = (
            f"CURRENT ROADMAP:\n{json.dumps(roadmap_summary, indent=2)}\n\n"
            f"PROGRESS RECORDS:\n{json.dumps(progress_summary, indent=2)}\n\n"
            f"QUALITATIVE FEEDBACK:\n{json.dumps(feedback_summary, indent=2)}\n\n"
            f"DEVIATION ANALYSIS:\n{json.dumps(deviation_summary, indent=2)}\n\n"
            "Please analyze these signals and produce an AdaptationProposal to recalibrate the curriculum."
        )

        messages = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_content),
        ]

        reservation = None
        if self.budget_manager:
            reservation = self.budget_manager.reserve(
                workflow=LLMWorkflow.ADAPTATION,
                operation="propose_adaptation",
                estimated_requests=1,
            )

        try:
            proposal = self.llm_provider.complete(
                messages=messages,
                response_model=AdaptationProposal,
            )
            if self.budget_manager and reservation:
                self.budget_manager.commit(reservation, success=True)
            return proposal
        except Exception as exc:
            if self.budget_manager and reservation:
                self.budget_manager.commit(
                    reservation,
                    success=False,
                    failure_category=FailureCategory.UNKNOWN_PROVIDER_ERROR,
                    error_message=str(exc),
                )
            logger.error("AdaptationAgent failed to propose adaptation", error=str(exc))
            raise
