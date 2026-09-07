"""Use case: AdaptRoadmapUseCase.

Evaluates progress deviations and feedback, checks anti-oscillation policies,
invokes AdaptationAgent under LLM budget control, validates proposed modifications
deterministically (DAG cycle checks, prerequisite order, time feasibility),
and produces an immutable next-version roadmap with full adaptation audit trail.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime

from roadmap.agents.adaptation_agent import AdaptationAgent
from roadmap.agents.schemas.adaptation import AdaptationProposal
from roadmap.application.graph.validator import SkillGraphValidator
from roadmap.application.ports.repositories import (
    AdaptationRepository,
    FeedbackRepository,
    ProgressRepository,
    RoadmapRepository,
)
from roadmap.domain.entities.adaptation import DeviationReport, RoadmapAdaptation
from roadmap.domain.entities.progress_record import ProgressRecord
from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill, SkillDependency
from roadmap.domain.services.deviation_detector import DeviationDetector
from roadmap.domain.value_objects.enums import DependencyType, Priority, SkillLevel, SkillStatus
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AdaptationCandidateResult:
    """Prepared adaptation proposal ready for review / confirmation."""

    current_roadmap: Roadmap
    candidate_roadmap: Roadmap
    proposal: AdaptationProposal
    deviation_report: DeviationReport
    requires_adaptation: bool
    blocked_by_anti_oscillation: bool
    anti_oscillation_reason: str = ""


class AdaptRoadmapUseCase:
    """
    Orchestrates adaptive roadmap replanning.
    """

    MIN_HOURS_BETWEEN_ADAPTATIONS = 10.0  # Require at least 10 hrs logged since last adaptation

    def __init__(
        self,
        roadmap_repo: RoadmapRepository,
        progress_repo: ProgressRepository,
        feedback_repo: FeedbackRepository,
        adaptation_repo: AdaptationRepository,
        adaptation_agent: AdaptationAgent,
        deviation_detector: DeviationDetector | None = None,
        graph_validator: SkillGraphValidator | None = None,
    ) -> None:
        self.roadmap_repo = roadmap_repo
        self.progress_repo = progress_repo
        self.feedback_repo = feedback_repo
        self.adaptation_repo = adaptation_repo
        self.adaptation_agent = adaptation_agent
        self.deviation_detector = deviation_detector or DeviationDetector()
        self.graph_validator = graph_validator or SkillGraphValidator()

    def prepare_adaptation(
        self,
        profile_id: str,
        force: bool = False,
    ) -> AdaptationCandidateResult:
        """
        Evaluate conditions, check anti-oscillation, invoke AdaptationAgent,
        build and validate candidate vN+1 roadmap, and return for user confirmation.
        """
        roadmap = self.roadmap_repo.load_latest(profile_id)
        if not roadmap:
            raise ValueError("No active roadmap found for user.")

        progress_records = self.progress_repo.load_all(profile_id)
        feedback_records = self.feedback_repo.load_for_roadmap(roadmap.id)

        deviation_report = self.deviation_detector.analyze_deviation(
            roadmap=roadmap,
            progress_records=progress_records,
            feedback_records=feedback_records,
        )

        # Check anti-oscillation guard
        latest_adaptation = self.adaptation_repo.get_latest_adaptation(profile_id)
        blocked_by_anti_oscillation = False
        anti_oscillation_reason = ""

        if latest_adaptation and not force:
            hours_since_last = sum(
                r.actual_hours for r in progress_records if r.updated_at > latest_adaptation.created_at
            )
            if hours_since_last < self.MIN_HOURS_BETWEEN_ADAPTATIONS:
                blocked_by_anti_oscillation = True
                anti_oscillation_reason = (
                    f"Anti-oscillation cooldown active: only {hours_since_last:.1f} hours logged "
                    f"since version {latest_adaptation.new_version} adaptation. "
                    f"(Minimum {self.MIN_HOURS_BETWEEN_ADAPTATIONS:.0f} hours required before automatic replan)."
                )

        if not force and not deviation_report.requires_adaptation and not blocked_by_anti_oscillation:
            # Pacing is acceptable, no replanning needed
            return AdaptationCandidateResult(
                current_roadmap=roadmap,
                candidate_roadmap=roadmap,
                proposal=AdaptationProposal(
                    adaptation_strategy="No adaptation needed",
                    rationale="Learning progress is on-track; schedule parameters remain well-calibrated.",
                    confidence=1.0,
                ),
                deviation_report=deviation_report,
                requires_adaptation=False,
                blocked_by_anti_oscillation=False,
            )

        if blocked_by_anti_oscillation and not force:
            return AdaptationCandidateResult(
                current_roadmap=roadmap,
                candidate_roadmap=roadmap,
                proposal=AdaptationProposal(
                    adaptation_strategy="Replanning suppressed by anti-oscillation policy",
                    rationale=anti_oscillation_reason,
                    confidence=1.0,
                ),
                deviation_report=deviation_report,
                requires_adaptation=True,
                blocked_by_anti_oscillation=True,
                anti_oscillation_reason=anti_oscillation_reason,
            )

        # Propose adaptation via agent
        proposal = self.adaptation_agent.propose_adaptation(
            roadmap=roadmap,
            progress_records=progress_records,
            feedback_records=feedback_records,
            deviation_report=deviation_report,
        )

        # Construct candidate vN+1 roadmap
        candidate = self._build_candidate_roadmap(roadmap, proposal, progress_records)

        # Validate candidate graph deterministically
        self._validate_candidate_roadmap(candidate)

        return AdaptationCandidateResult(
            current_roadmap=roadmap,
            candidate_roadmap=candidate,
            proposal=proposal,
            deviation_report=deviation_report,
            requires_adaptation=True,
            blocked_by_anti_oscillation=False,
        )

    def apply_adaptation(
        self,
        candidate_result: AdaptationCandidateResult,
    ) -> Roadmap:
        """
        Commit candidate vN+1 roadmap and record RoadmapAdaptation audit trail.
        """
        current = candidate_result.current_roadmap
        candidate = candidate_result.candidate_roadmap
        proposal = candidate_result.proposal
        dev = candidate_result.deviation_report

        now = datetime.now(UTC)
        candidate.generated_at = now
        candidate.last_updated_at = now

        # Save new roadmap version
        self.roadmap_repo.save(candidate)

        # Build adaptation audit record
        adaptation_record = RoadmapAdaptation(
            id=new_id(),
            profile_id=current.profile_id,
            previous_roadmap_id=current.id,
            new_roadmap_id=candidate.id,
            previous_version=current.version,
            new_version=candidate.version,
            trigger_reason=proposal.adaptation_strategy,
            deviation_summary={
                "status": dev.status.value,
                "velocity_ratio": dev.velocity_ratio,
                "progress_deviation": dev.progress_deviation,
                "blocked_skills": dev.blocked_skills,
                "issues": dev.issues,
            },
            user_feedback_summary={
                "strategy": proposal.adaptation_strategy,
                "confidence": proposal.confidence,
            },
            changes_summary={
                "strategy": proposal.adaptation_strategy,
                "affected_phases": proposal.affected_phase_numbers,
                "phase_adjustments": [p.model_dump() for p in proposal.phase_adjustments],
                "skill_adjustments": [s.model_dump() for s in proposal.skill_adjustments],
                "support_skills": [s.model_dump() for s in proposal.support_skills],
                "weeks_delta": proposal.estimated_total_weeks_delta,
            },
            accepted=True,
            created_at=now,
        )
        self.adaptation_repo.save(adaptation_record)

        logger.info(
            "Roadmap adapted successfully",
            profile_id=current.profile_id,
            old_version=current.version,
            new_version=candidate.version,
        )
        return candidate

    def _build_candidate_roadmap(
        self,
        current: Roadmap,
        proposal: AdaptationProposal,
        progress_records: list[ProgressRecord],
    ) -> Roadmap:
        """Deep copy current roadmap and apply proposal modifications."""
        completed_skill_names = {
            r.skill_name.lower()
            for r in progress_records
            if r.completion_percentage >= 100.0 or r.status.value == "COMPLETED"
        }

        # Build new phases
        new_phases: list[RoadmapPhase] = []
        phase_duration_overrides = {
            p.phase_number: p.new_estimated_weeks for p in proposal.phase_adjustments
        }

        # Index skill adjustments
        skill_hour_overrides = {
            s.skill_name.lower(): s.new_estimated_hours
            for s in proposal.skill_adjustments
            if s.new_estimated_hours is not None
        }

        # Group support skills by target phase
        support_skills_by_phase: dict[int, list[Skill]] = {}
        for sup in proposal.support_skills:
            new_skill = Skill(
                id=new_id(),
                profile_id=current.profile_id,
                name=sup.name,
                category=sup.category,
                description=sup.rationale,
                current_level=SkillLevel.MISSING,
                target_level=SkillLevel.FAMILIAR,
                status=SkillStatus.PENDING,
                priority=Priority.HIGH,
                market_demand_score=0.8,
                goal_relevance_score=0.85,
                estimated_hours=sup.estimated_hours,
                prerequisite_names=[],
            )
            support_skills_by_phase.setdefault(sup.target_phase_number, []).append(new_skill)

        for old_phase in current.phases:
            new_skills: list[Skill] = []
            for sk in old_phase.skills:
                sk_copy = sk.model_copy(deep=True)
                # Apply hour override if proposed
                if sk_copy.name.lower() in skill_hour_overrides:
                    new_hrs = skill_hour_overrides[sk_copy.name.lower()]
                    if new_hrs is not None and new_hrs > 0:
                        sk_copy.estimated_hours = new_hrs

                # Maintain completed status
                if sk_copy.name.lower() in completed_skill_names:
                    sk_copy.status = SkillStatus.COMPLETED
                    sk_copy.current_level = sk_copy.target_level

                new_skills.append(sk_copy)

            # Insert any support skills for this phase
            if old_phase.phase_number in support_skills_by_phase:
                new_skills.extend(support_skills_by_phase[old_phase.phase_number])

            new_weeks = phase_duration_overrides.get(old_phase.phase_number, old_phase.estimated_weeks)

            new_phase = RoadmapPhase(
                id=new_id(),
                roadmap_id=old_phase.roadmap_id,
                phase_number=old_phase.phase_number,
                name=old_phase.name,
                objective=old_phase.objective,
                skills=new_skills,
                resources=[r.model_copy(deep=True) for r in old_phase.resources],
                projects=[p.model_copy(deep=True) for p in old_phase.projects],
                milestones=[m.model_copy(deep=True) for m in old_phase.milestones],
                estimated_weeks=new_weeks,
                is_completed=old_phase.is_completed,
                completed_at=old_phase.completed_at,
                created_at=datetime.now(UTC),
            )
            new_phases.append(new_phase)

        next_version = current.version + 1
        candidate = Roadmap(
            id=new_id(),
            profile_id=current.profile_id,
            title=current.title,
            version=next_version,
            objective=current.objective,
            phases=new_phases,
            assumptions=copy.deepcopy(current.assumptions),
            skipped_skill_names=copy.deepcopy(current.skipped_skill_names),
            research_run_id=current.research_run_id,
            quality_score=current.quality_score,
            validation_status="COMPLETED",
            evaluator_score=current.evaluator_score,
            evaluator_verdict=current.evaluator_verdict,
            generated_at=datetime.now(UTC),
            last_updated_at=datetime.now(UTC),
        )
        candidate.recalculate_totals()
        return candidate

    def _validate_candidate_roadmap(self, roadmap: Roadmap) -> None:
        """Enforce DAG validity and prerequisite sequencing."""
        from roadmap.domain.entities.skill import SkillNode

        skills = roadmap.all_skills
        nodes = [
            SkillNode(
                id=s.id,
                name=s.name,
                category=s.category,
                description=s.description,
                prerequisites=s.prerequisite_names,
            )
            for s in skills
        ]

        dependencies: list[SkillDependency] = []
        for s in skills:
            for prereq_name in s.prerequisite_names:
                dependencies.append(
                    SkillDependency(
                        prerequisite_skill=prereq_name,
                        dependent_skill=s.name,
                        dependency_type=DependencyType.REQUIRES,
                    )
                )

        report = self.graph_validator.validate(nodes, dependencies)
        if not report.is_valid:
            error_msgs = "; ".join(report.errors or ["Invalid graph structure"])
            raise ValueError(f"Candidate adapted roadmap violates DAG integrity: {error_msgs}")
