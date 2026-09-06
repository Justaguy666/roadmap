"""Application service: RoadmapRevisionLoop.

Executes a bounded feedback loop between:
1. Candidate Roadmap Generation (LLM Planner)
2. Deterministic Roadmap Validation (RoadmapValidator & SkillGraphValidator)
3. Evaluator Agent Critique (RoadmapEvaluator)
4. Bounded Revision (max 3 cycles)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from roadmap.agents.evaluator import RoadmapEvaluator
from roadmap.agents.prompts.roadmap_generation import (
    ROADMAP_GENERATION_SYSTEM_PROMPT,
    build_roadmap_revision_prompt,
)
from roadmap.agents.schemas.evaluator import RoadmapEvaluationResult
from roadmap.agents.schemas.roadmap_generation import RoadmapGenerationResult
from roadmap.application.graph.builder import SkillGraphBuilder
from roadmap.application.ports.llm_provider import LLMMessage, LLMProvider
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.config.settings import settings
from roadmap.domain.entities.evidence_aggregation import SkillEvidenceSummary
from roadmap.domain.entities.skill import SkillDependency, SkillNode
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.services.roadmap_validator import RoadmapValidator
from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class RoadmapRevisionLoop:
    """Coordinates deterministic validation and evaluator feedback across up to max_iterations."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        evaluator: RoadmapEvaluator,
        max_iterations: int = 3,
        budget_manager: LLMBudgetManager | None = None,
    ) -> None:
        self.llm = llm_provider
        self.evaluator = evaluator
        self.max_iterations = max_iterations
        self.budget_manager = budget_manager

    def run_loop(
        self,
        initial_candidate: RoadmapGenerationResult,
        profile: UserProfile,
        target_role: str,
        target_goal: str,
        evidence_summaries: dict[str, SkillEvidenceSummary],
        market_summary_list: list[dict[str, Any]],
        progress_callback: Callable[[str], None] | None = None,
    ) -> tuple[RoadmapGenerationResult, RoadmapEvaluationResult, list[str]]:
        """
        Execute bounded repair loop.

        Returns (best_or_final_draft, final_evaluation_result, accumulated_warnings).
        """
        current_candidate = initial_candidate
        warnings: list[str] = []
        final_evaluation: RoadmapEvaluationResult | None = None

        weekly_hours = max(1.0, profile.study_hours_per_week)
        deadline_weeks = max(1.0, profile.deadline_months * 4.33)

        for iteration in range(1, self.max_iterations + 1):
            msg = f"Revision loop cycle {iteration}/{self.max_iterations}: validating candidate roadmap..."
            if progress_callback:
                progress_callback(msg)
            logger.info("Revision loop iteration", iteration=iteration, max_iterations=self.max_iterations)

            # 1. Deterministic Validation
            det_errors: list[str] = []

            # (a) Check duplicate skills within candidate
            all_candidate_skills: list[str] = []
            for p in current_candidate.phases:
                for s in p.skills:
                    if s.name.lower() in [x.lower() for x in all_candidate_skills]:
                        det_errors.append(f"Duplicate skill in candidate: '{s.name}'")
                    all_candidate_skills.append(s.name)

            # (b) Time feasibility check
            total_candidate_hours = sum(s.estimated_hours for p in current_candidate.phases for s in p.skills)
            weeks_needed = total_candidate_hours / weekly_hours
            if weeks_needed > deadline_weeks * 1.30:
                det_errors.append(
                    f"Workload infeasible: requires {int(weeks_needed)} weeks (>30% overrun) against target of {deadline_weeks} weeks."
                )

            # (c) Graph cycle validation on proposed prerequisites
            nodes = [
                SkillNode(name=s.name, category=s.category, estimated_hours=s.estimated_hours)
                for p in current_candidate.phases
                for s in p.skills
            ]
            deps = [
                SkillDependency(prerequisite_skill=prereq, dependent_skill=s.name)
                for p in current_candidate.phases
                for s in p.skills
                for prereq in s.prerequisites
            ]
            _, _, graph_val = SkillGraphBuilder.build(nodes, deps)
            if not graph_val.is_valid:
                det_errors.extend(graph_val.errors)

            # (d) Full deterministic roadmap validation (phase ordering, empty phases, etc.)
            val_checker = RoadmapValidator()
            # Construct a temporary domain roadmap to run validator
            from roadmap.domain.entities.roadmap import Milestone, Roadmap, RoadmapPhase
            from roadmap.domain.entities.skill import Skill
            temp_phases = []
            for p_idx, pd in enumerate(current_candidate.phases, start=1):
                temp_skills = [
                    Skill(
                        profile_id=profile.id,
                        name=sd.name,
                        estimated_hours=sd.estimated_hours,
                        prerequisite_names=sd.prerequisites,
                    )
                    for sd in pd.skills
                ]
                temp_milestones = [
                    Milestone(
                        phase_id="",
                        name=m.measurable_outcome,
                        exit_criteria=m.exit_criteria,
                    )
                    for m in pd.milestones
                ]
                temp_phases.append(RoadmapPhase(
                    roadmap_id="",
                    phase_number=p_idx,
                    name=pd.phase_name,
                    objective=pd.objective,
                    skills=temp_skills,
                    milestones=temp_milestones,
                    estimated_weeks=pd.estimated_duration_weeks,
                ))
            temp_roadmap = Roadmap(
                profile_id=profile.id,
                title="Validation Check",
                phases=temp_phases,
                total_weeks=int(sum(p.estimated_weeks for p in temp_phases)),
            )
            temp_roadmap.recalculate_totals()
            det_val_res = val_checker.validate(temp_roadmap, profile)
            if not det_val_res.is_valid:
                det_errors.extend([e.message for e in det_val_res.errors])

            # 2. Run Evaluator Agent
            candidate_dict = current_candidate.model_dump()
            evaluation = self.evaluator.evaluate(
                target_role=target_role,
                target_goal=target_goal,
                weekly_hours=weekly_hours,
                deadline_weeks=deadline_weeks,
                candidate_roadmap_dict=candidate_dict,
                market_summary_list=market_summary_list,
                deterministic_errors=det_errors,
            )
            final_evaluation = evaluation

            logger.info(
                "Evaluator verdict received",
                iteration=iteration,
                verdict=evaluation.verdict,
                score=evaluation.score,
                issues_count=len(evaluation.issues),
            )

            # Check if candidate passes
            if evaluation.verdict == "PASS" and not det_errors:
                if progress_callback:
                    progress_callback(f"Candidate passed evaluation with quality score {evaluation.score:.1f}/100!")
                return current_candidate, evaluation, warnings

            # If we reached max iterations, break and accept best draft with warnings
            if iteration >= self.max_iterations:
                warn = f"Reached maximum {self.max_iterations} revision attempts. Accepting best available draft with warnings."
                warnings.append(warn)
                if progress_callback:
                    progress_callback(warn)
                break

            # 3. Formulate targeted revision prompt
            if progress_callback:
                progress_callback(f"Evaluator requested REVISE ({len(evaluation.issues)} issues, {len(det_errors)} errors). Revising...")

            revision_prompt = build_roadmap_revision_prompt(
                original_roadmap_json=candidate_dict,
                evaluator_issues=[i.model_dump() for i in evaluation.issues],
                deterministic_errors=det_errors,
                recommendations=evaluation.recommendations,
            )

            rev_messages = [
                LLMMessage(role="system", content=ROADMAP_GENERATION_SYSTEM_PROMPT),
                LLMMessage(role="user", content=revision_prompt),
            ]

            reservation = None
            if self.budget_manager:
                try:
                    reservation = self.budget_manager.reserve(
                        workflow=LLMWorkflow.GENERATION,
                        operation=f"revision_cycle_{iteration}",
                        estimated_requests=1,
                    )
                except Exception as b_exc:
                    warn = f"Revision budget exhausted at cycle {iteration}: {b_exc}. Stopping revision loop."
                    warnings.append(warn)
                    logger.warning(warn)
                    if progress_callback:
                        progress_callback(warn)
                    break

            try:
                revised_draft: RoadmapGenerationResult = self.llm.complete(
                    messages=rev_messages,
                    response_model=RoadmapGenerationResult,
                    temperature=0.2,
                )
                if self.budget_manager and reservation:
                    self.budget_manager.commit(
                        reservation=reservation,
                        success=True,
                        provider=settings.llm_provider,
                        model=settings.llm_model or "default",
                        actual_requests=1,
                    )
                current_candidate = revised_draft
            except Exception as exc:
                if self.budget_manager and reservation:
                    fc = getattr(exc, "failure_category", FailureCategory.UNKNOWN_PROVIDER_ERROR)
                    self.budget_manager.commit(
                        reservation=reservation,
                        success=False,
                        failure_category=fc,
                        provider=settings.llm_provider,
                        model=settings.llm_model or "default",
                        actual_requests=1,
                        error_message=str(exc),
                    )
                warn = f"Revision LLM call failed in iteration {iteration}: {exc}. Preserving prior candidate."
                warnings.append(warn)
                logger.warning(warn)
                break

        # Fallback evaluation if loop exited without one
        if final_evaluation is None:
            final_evaluation = RoadmapEvaluationResult(
                verdict="PASS",
                score=75.0,
                issues=[],
                warnings=warnings,
            )

        return current_candidate, final_evaluation, warnings
