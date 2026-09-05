"""
Application use case: GenerateRoadmapUseCase.

Orchestrates the full end-to-end roadmap generation pipeline:
  User Profile
      ↓
  Goal Analysis
      ↓
  Skill Gap Analysis (deterministic)
      ↓
  Roadmap Generation (LLM)
      ↓
  Deterministic Validation (RoadmapValidator)
      ↓
  Bounded Repair / Retry if needed
      ↓
  Persistence (RoadmapRepository, SkillRepository)
"""

from __future__ import annotations

import time
from collections.abc import Callable

from roadmap.agents.evaluator import RoadmapEvaluator
from roadmap.agents.prompts.roadmap_generation import (
    ROADMAP_GENERATION_SYSTEM_PROMPT,
    build_evidence_grounded_roadmap_prompt,
    build_roadmap_generation_user_prompt,
)
from roadmap.agents.schemas.goal_analysis import GoalAnalysisResult
from roadmap.agents.schemas.roadmap_generation import (
    RoadmapGenerationResult,
)
from roadmap.agents.schemas.skill_gap import (
    SkillGapAnalysisResult,
    SkillGapItem,
)
from roadmap.application.graph.builder import SkillGraphBuilder
from roadmap.application.ports.llm_provider import LLMMessage, LLMProvider
from roadmap.application.ports.repositories import (
    EvidenceRepository,
    ProfileRepository,
    RecommendationRepository,
    RoadmapRepository,
    SkillRepository,
    SourceRepository,
)
from roadmap.application.services.roadmap_revision_loop import RoadmapRevisionLoop
from roadmap.application.use_cases.analyze_goal import AnalyzeGoalUseCase
from roadmap.domain.entities.evidence_aggregation import (
    MarketObservation,
    SkillEvidenceSummary,
)
from roadmap.domain.entities.learning_resource import LearningResource, Project
from roadmap.domain.entities.roadmap import Milestone, Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill, SkillDependency, SkillNode
from roadmap.domain.entities.source import Recommendation
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import RoadmapValidationError
from roadmap.domain.services.evidence_aggregator import EvidenceAggregator
from roadmap.domain.services.market_intelligence import MarketIntelligenceService
from roadmap.domain.services.priority_calculator import PriorityCalculator
from roadmap.domain.services.quality_scorer import QualityScorer
from roadmap.domain.services.roadmap_decision_service import RoadmapDecisionService
from roadmap.domain.services.roadmap_validator import RoadmapValidator, ValidationResult
from roadmap.domain.services.skill_gap_analyzer import SkillGapAnalyzer
from roadmap.domain.value_objects import DependencyType, SkillStatus
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class GenerateRoadmapUseCase:
    """
    Orchestrates the creation, evidence grounding, evaluation, and validation of a learning roadmap.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        profile_repo: ProfileRepository,
        roadmap_repo: RoadmapRepository,
        skill_repo: SkillRepository,
        evidence_repo: EvidenceRepository | None = None,
        source_repo: SourceRepository | None = None,
        recommendation_repo: RecommendationRepository | None = None,
        max_retries: int = 3,
    ) -> None:
        self.llm_provider = llm_provider
        self.profile_repo = profile_repo
        self.roadmap_repo = roadmap_repo
        self.skill_repo = skill_repo
        self.evidence_repo = evidence_repo
        self.source_repo = source_repo
        self.recommendation_repo = recommendation_repo
        self.max_retries = max_retries

        self.goal_analyzer = AnalyzeGoalUseCase(llm_provider)
        self.gap_analyzer = SkillGapAnalyzer()
        self.priority_calculator = PriorityCalculator()
        self.validator = RoadmapValidator()
        self.evaluator = RoadmapEvaluator(llm_provider)
        self.revision_loop = RoadmapRevisionLoop(
            llm_provider=llm_provider,
            evaluator=self.evaluator,
            max_iterations=max_retries,
        )

    def execute(
        self,
        profile: UserProfile,
        existing_goal_analysis: GoalAnalysisResult | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> tuple[Roadmap, GoalAnalysisResult, SkillGapAnalysisResult, ValidationResult]:
        """
        Execute the full roadmap generation pipeline with evidence grounding and revision loop.
        """
        start_time = time.perf_counter()
        logger.info("Initiating roadmap generation pipeline", profile_id=profile.id)

        # 1. Goal Analysis (or reuse precomputed)
        if existing_goal_analysis is not None:
            goal_analysis = existing_goal_analysis
            logger.info("Using existing goal analysis result")
        else:
            if progress_callback:
                progress_callback("Analyzing career goals and competencies...")
            goal_analysis = self.goal_analyzer.execute(profile)

        # 2. Deterministic Skill Gap Analysis
        if progress_callback:
            progress_callback("Calculating skill gaps...")
        skill_gaps = self._compute_skill_gaps(profile, goal_analysis)

        # 3. Evidence Aggregation & Market Intelligence (if research data exists)
        evidence_summaries, market_observations = self._aggregate_research_context()

        # 4. Construct Initial Skill Graph & Topological Pre-Ordering
        topo_order, skill_graph_nodes, skill_graph_edges = self._build_initial_graph(
            goal_analysis=goal_analysis,
            skill_gaps=skill_gaps,
            evidence_summaries=evidence_summaries,
        )

        # 5. Candidate Generation
        if progress_callback:
            progress_callback("Drafting candidate roadmap...")
        candidate_draft = self._generate_candidate(
            profile=profile,
            goal_analysis=goal_analysis,
            skill_gaps=skill_gaps,
            evidence_summaries=evidence_summaries,
            topo_order=topo_order,
        )

        # 6. Revision Loop (Deterministic Validation + Evaluator Agent Critique)
        market_summary_list = [
            {
                "skill": obs.skill_name,
                "mentions": obs.mentions,
                "sample_size": obs.sample_size,
                "frequency": obs.observed_frequency,
                "companies": obs.unique_companies,
                "regions": obs.market_regions,
            }
            for obs in market_observations.values()
        ]

        final_draft, evaluation_res, loop_warnings = self.revision_loop.run_loop(
            initial_candidate=candidate_draft,
            profile=profile,
            target_role=goal_analysis.target_role,
            target_goal=goal_analysis.interpreted_goal,
            evidence_summaries=evidence_summaries,
            market_summary_list=market_summary_list,
            progress_callback=progress_callback,
        )

        # 7. Convert draft to domain Roadmap entity with versioning
        roadmap = self._to_domain_roadmap(
            profile=profile,
            draft=final_draft,
            evidence_summaries=evidence_summaries,
        )

        # 8. Deterministic Validation Check
        val_result = self.validator.validate(roadmap, profile)
        if not val_result.is_valid:
            error_messages = [e.message for e in val_result.errors]
            logger.error("Roadmap failed validation", errors=error_messages)
            raise RoadmapValidationError(error_messages)

        # 9. Compute Deterministic Quality Score
        quality_score = QualityScorer.calculate_score(
            roadmap=roadmap,
            profile=profile,
            evidence_summaries=evidence_summaries,
            has_cycles=False,
        )
        roadmap.quality_score = quality_score.overall_score

        # 10. Persist Roadmap, Skills, and Dependencies
        if hasattr(self.roadmap_repo, "get_next_version"):
            next_ver = self.roadmap_repo.get_next_version(profile.id)  # type: ignore[union-attr]
            roadmap.version = next_ver

        self.roadmap_repo.save(roadmap)
        self.skill_repo.save_skills(roadmap.all_skills)

        dependencies = self._extract_dependencies(roadmap)
        if dependencies:
            self.skill_repo.save_dependencies(dependencies)

        # 11. Persist Skill Decisions & Recommendations
        self._persist_recommendations(
            roadmap=roadmap,
            evidence_summaries=evidence_summaries,
            market_observations=market_observations,
            dependencies=dependencies,
        )

        total_duration = time.perf_counter() - start_time
        logger.info(
            "Roadmap generation pipeline completed and persisted",
            roadmap_id=roadmap.id,
            version=roadmap.version,
            total_phases=len(roadmap.phases),
            total_skills=len(roadmap.all_skills),
            quality_score=roadmap.quality_score,
            duration_seconds=round(total_duration, 2),
        )

        return roadmap, goal_analysis, skill_gaps, val_result

    def _aggregate_research_context(
        self,
    ) -> tuple[dict[str, SkillEvidenceSummary], dict[str, MarketObservation]]:
        """Retrieve persisted evidence and sources, aggregating summaries."""
        if not self.evidence_repo or not self.source_repo:
            return {}, {}

        try:
            all_evidence = self.evidence_repo.list_all(limit=500) if hasattr(self.evidence_repo, "list_all") else []  # type: ignore[union-attr]
            all_sources = self.source_repo.list_all(limit=200) if hasattr(self.source_repo, "list_all") else []  # type: ignore[union-attr]

            if not all_evidence or not all_sources:
                return {}, {}

            sources_by_id = {s.id: s for s in all_sources}
            evidence_summaries = EvidenceAggregator.aggregate_all(all_evidence, all_sources)
            market_obs = MarketIntelligenceService.analyze_market_sample(
                target_role="",
                evidence_items=all_evidence,
                sources_by_id=sources_by_id,
            )
            return evidence_summaries, market_obs
        except Exception as exc:
            logger.warning("Failed to aggregate research context", error=str(exc))
            return {}, {}

    def _build_initial_graph(
        self,
        goal_analysis: GoalAnalysisResult,
        skill_gaps: SkillGapAnalysisResult,
        evidence_summaries: dict[str, SkillEvidenceSummary],
    ) -> tuple[list[str], list[SkillNode], list[SkillDependency]]:
        """Construct initial skill nodes and dependency graph."""
        nodes: list[SkillNode] = []
        deps: list[SkillDependency] = []

        for req in goal_analysis.required_skills:
            ev_summary = evidence_summaries.get(req.name)
            ev_ids = ev_summary.supporting_evidence_ids if ev_summary else []
            nodes.append(
                SkillNode(
                    name=req.name,
                    category=req.category,
                    description=req.description,
                    target_level=req.target_level,
                    priority=req.priority,
                    estimated_hours=30.0,
                    evidence_ids=ev_ids,
                )
            )

        node_list, normalized_deps, val_result = SkillGraphBuilder.build(nodes, deps)
        sorted_skills = val_result.topological_order if val_result.topological_order else [n.name for n in node_list]
        return sorted_skills, node_list, normalized_deps

    def _generate_candidate(
        self,
        profile: UserProfile,
        goal_analysis: GoalAnalysisResult,
        skill_gaps: SkillGapAnalysisResult,
        evidence_summaries: dict[str, SkillEvidenceSummary],
        topo_order: list[str],
    ) -> RoadmapGenerationResult:
        """Call LLM planner to draft the candidate roadmap."""
        ev_summary_list = [
            {
                "skill": s.skill_name,
                "weighted_score": s.weighted_score,
                "evidence_count": s.evidence_count,
                "sources_count": s.unique_source_count,
                "evidence_ids": s.supporting_evidence_ids,
                "divergence_notes": s.divergence_notes,
            }
            for s in evidence_summaries.values()
            if s.evidence_count > 0
        ]

        if ev_summary_list:
            user_prompt = build_evidence_grounded_roadmap_prompt(
                profile=profile,
                goal_analysis=goal_analysis,
                skill_gaps=skill_gaps,
                evidence_summaries=ev_summary_list,
                skill_graph_ordering=topo_order,
            )
        else:
            user_prompt = build_roadmap_generation_user_prompt(
                profile=profile,
                goal_analysis=goal_analysis,
                skill_gaps=skill_gaps,
            )

        messages = [
            LLMMessage(role="system", content=ROADMAP_GENERATION_SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        ]

        draft: RoadmapGenerationResult = self.llm_provider.complete(
            messages=messages,
            response_model=RoadmapGenerationResult,
        )
        return draft

    def _compute_skill_gaps(
        self,
        profile: UserProfile,
        goal_analysis: GoalAnalysisResult,
    ) -> SkillGapAnalysisResult:
        """
        Deterministically compare user's reported skills against goal requirements.
        """
        current_map = self.gap_analyzer.build_current_skill_map(profile.current_skills)

        domain_skills = [
            Skill(
                id=new_id(),
                profile_id=profile.id,
                name=req.name,
                category=req.category,
                target_level=req.target_level,
                priority=req.priority,
                description=req.description,
            )
            for req in goal_analysis.required_skills
        ]

        report = self.gap_analyzer.analyze(current_map, domain_skills)

        gap_items: list[SkillGapItem] = []
        for gap in report.missing_skills:
            req_info = next((s for s in goal_analysis.required_skills if s.name.lower() == gap.skill_name.lower()), None)
            reason = req_info.rationale if req_info else "Required core competency"
            gap_items.append(SkillGapItem(
                skill=gap.skill_name,
                category=req_info.category if req_info else "general",
                current_level=gap.current_level,
                target_level=gap.target_level,
                gap=gap.level_gap,
                priority=gap.priority,
                reasoning=f"Missing foundational skill. {reason}",
            ))

        for gap in report.partial_skills:
            req_info = next((s for s in goal_analysis.required_skills if s.name.lower() == gap.skill_name.lower()), None)
            reason = req_info.rationale if req_info else "Improvement needed to meet role standard"
            gap_items.append(SkillGapItem(
                skill=gap.skill_name,
                category=req_info.category if req_info else "general",
                current_level=gap.current_level,
                target_level=gap.target_level,
                gap=gap.level_gap,
                priority=gap.priority,
                reasoning=f"Partial mastery. {reason}",
            ))

        for comp in report.completed_skills:
            gap_items.append(SkillGapItem(
                skill=comp.skill_name,
                category="general",
                current_level=comp.current_level,
                target_level=comp.target_level,
                gap=0,
                priority=comp.priority,
                reasoning="Already satisfies role requirements.",
            ))

        return SkillGapAnalysisResult(
            interpreted_goal=goal_analysis.interpreted_goal,
            target_role=goal_analysis.target_role,
            gaps=gap_items,
            total_gaps=report.total_actionable,
            critical_gaps_count=len(report.critical_gaps()),
            completion_rate=report.completion_rate,
            summary_notes=[
                f"Candidate currently possesses {len(report.completed_skills)} out of {len(domain_skills)} required competencies.",
                f"Needs to bridge {len(report.missing_skills)} missing skills and upgrade {len(report.partial_skills)} partial skills.",
            ],
        )

    def _generate_and_validate(
        self,
        profile: UserProfile,
        goal_analysis: GoalAnalysisResult,
        skill_gaps: SkillGapAnalysisResult,
    ) -> tuple[RoadmapGenerationResult, Roadmap, ValidationResult]:
        """
        Request LLM completion and validate. Retries with feedback if validation fails.
        """
        initial_user_prompt = build_roadmap_generation_user_prompt(
            profile=profile,
            goal_analysis=goal_analysis,
            skill_gaps=skill_gaps,
        )

        messages = [
            LLMMessage.system(ROADMAP_GENERATION_SYSTEM_PROMPT),
            LLMMessage.user(initial_user_prompt),
        ]

        last_draft: RoadmapGenerationResult | None = None
        last_roadmap: Roadmap | None = None
        last_val_result: ValidationResult | None = None

        for attempt in range(1, self.max_retries + 1):
            logger.info("Requesting roadmap draft generation", attempt=attempt, max_retries=self.max_retries)
            draft: RoadmapGenerationResult = self.llm_provider.complete(
                messages=messages,
                response_model=RoadmapGenerationResult,
            )
            last_draft = draft

            # Convert to domain model
            roadmap = self._to_domain_roadmap(profile, draft)
            last_roadmap = roadmap

            # Validate against deterministic rules
            val_result = self.validator.validate(roadmap, profile)
            last_val_result = val_result

            if val_result.is_valid:
                logger.info("Roadmap draft passed all validation checks", attempt=attempt)
                return draft, roadmap, val_result

            # Prepare repair prompt for next attempt
            error_details = [f"- {err.message} (affected: {err.affected})" for err in val_result.errors]
            warning_details = [f"- {warn.message}" for warn in val_result.warnings]

            repair_message = (
                "The generated roadmap draft was invalid. Please resolve the following errors:\n"
                + "\n".join(error_details)
            )
            if warning_details:
                repair_message += "\nWarnings to address if possible:\n" + "\n".join(warning_details)

            logger.warning(
                "Roadmap validation failed, sending repair feedback",
                attempt=attempt,
                errors=[e.message for e in val_result.errors],
            )

            # Append assistant's previous response and system repair request
            messages.append(LLMMessage.assistant(draft.model_dump_json()))
            messages.append(LLMMessage.user(repair_message))

        # If loops exhausted, return whatever was last obtained
        assert last_draft is not None and last_roadmap is not None and last_val_result is not None
        return last_draft, last_roadmap, last_val_result

    def _to_domain_roadmap(
        self,
        profile: UserProfile,
        draft: RoadmapGenerationResult,
        evidence_summaries: dict[str, SkillEvidenceSummary] | None = None,
    ) -> Roadmap:
        """Convert structured RoadmapGenerationResult into a domain Roadmap entity."""
        roadmap_id = new_id()
        domain_phases: list[RoadmapPhase] = []
        evidence_map = evidence_summaries or {}

        for phase_idx, pd in enumerate(draft.phases, start=1):
            phase_id = new_id()

            # Map skills with attached evidence
            skills: list[Skill] = []
            for sd in pd.skills:
                ev_ids = list(sd.evidence_ids)
                if not ev_ids and sd.name in evidence_map:
                    ev_ids = evidence_map[sd.name].supporting_evidence_ids

                skills.append(
                    Skill(
                        id=new_id(),
                        profile_id=profile.id,
                        name=sd.name,
                        category=sd.category,
                        target_level=sd.target_level,
                        priority=sd.priority,
                        estimated_hours=sd.estimated_hours,
                        prerequisite_names=sd.prerequisites,
                        evidence_ids=ev_ids,
                        status=SkillStatus.PENDING,
                    )
                )

            # Map projects
            projects = [
                Project(
                    id=new_id(),
                    phase_id=phase_id,
                    name=proj.title,
                    description=proj.description,
                    required_skill_names=proj.skills_practiced,
                    difficulty=proj.difficulty,
                    expected_outcome=proj.expected_outcome,
                    portfolio_value=proj.portfolio_value,
                    estimated_hours=proj.estimated_hours,
                )
                for proj in pd.projects
            ]

            # Map milestones
            milestones = [
                Milestone(
                    id=new_id(),
                    phase_id=phase_id,
                    name=f"Milestone {m_idx}: {m.measurable_outcome[:60]}",
                    description=m.measurable_outcome,
                    exit_criteria=m.exit_criteria,
                    estimated_weeks=m.estimated_weeks,
                )
                for m_idx, m in enumerate(pd.milestones, start=1)
            ]

            # Map resources
            resources = [
                LearningResource(
                    id=new_id(),
                    phase_id=phase_id,
                    title=res.title,
                    resource_type=res.resource_type,
                    url=res.url,
                    provider=res.provider,
                    difficulty=res.difficulty,
                    estimated_hours=res.estimated_hours,
                )
                for res in pd.resources
            ]

            domain_phases.append(RoadmapPhase(
                id=phase_id,
                roadmap_id=roadmap_id,
                phase_number=phase_idx,
                name=pd.phase_name,
                objective=pd.objective,
                skills=skills,
                projects=projects,
                milestones=milestones,
                resources=resources,
                estimated_weeks=pd.estimated_duration_weeks,
            ))

        total_weeks = int(sum(p.estimated_weeks for p in domain_phases))
        title = f"{goal_title(profile.target_role or profile.target_goal)} Learning Roadmap"

        roadmap = Roadmap(
            id=roadmap_id,
            profile_id=profile.id,
            title=title,
            objective=draft.roadmap_objective,
            phases=domain_phases,
            total_weeks=total_weeks,
            assumptions=draft.assumptions,
        )
        roadmap.recalculate_totals()
        return roadmap

    def _extract_dependencies(self, roadmap: Roadmap) -> list[SkillDependency]:
        """Extract SkillDependency edges from prerequisite_names."""
        skill_name_to_id: dict[str, str] = {
            s.name.lower(): s.id for s in roadmap.all_skills
        }
        deps: list[SkillDependency] = []

        for skill in roadmap.all_skills:
            for prereq_name in skill.prerequisite_names:
                prereq_id = skill_name_to_id.get(prereq_name.lower())
                if prereq_id and prereq_id != skill.id:
                    deps.append(SkillDependency(
                        id=new_id(),
                        from_skill_id=prereq_id,
                        to_skill_id=skill.id,
                        prerequisite_skill=prereq_name,
                        dependent_skill=skill.name,
                        dependency_type=DependencyType.REQUIRES,
                        source="llm_generated",
                        evidence_ids=skill.evidence_ids,
                    ))
        return deps

    def _persist_recommendations(
        self,
        roadmap: Roadmap,
        evidence_summaries: dict[str, SkillEvidenceSummary],
        market_observations: dict[str, MarketObservation],
        dependencies: list[SkillDependency],
    ) -> None:
        """Persist structured skill decision factors as Recommendations."""
        if not self.recommendation_repo:
            return

        # Calculate dependent count for each skill
        dep_counts: dict[str, int] = {}
        for d in dependencies:
            prereq = d.prerequisite_skill.lower() if d.prerequisite_skill else d.from_skill_id
            dep_counts[prereq] = dep_counts.get(prereq, 0) + 1

        for skill in roadmap.all_skills:
            ev_summary = evidence_summaries.get(skill.name)
            market_obs = market_observations.get(skill.name)
            dependent_count = dep_counts.get(skill.name.lower(), 0)

            decision = RoadmapDecisionService.evaluate_skill(
                skill=skill,
                evidence_summary=ev_summary,
                market_obs=market_obs,
                dependent_count=dependent_count,
                estimated_hours=skill.estimated_hours,
            )

            rec = Recommendation(
                id=new_id(),
                skill_id=skill.id,
                roadmap_id=roadmap.id,
                decision=decision.decision,
                reasoning=decision.rationale,
                decision_factors=decision.factors.model_dump(),
                evidence_ids=decision.evidence_ids,
                confidence=decision.confidence,
            )
            try:
                self.recommendation_repo.save(rec)
            except Exception as exc:
                logger.warning("Failed to save recommendation", skill=skill.name, error=str(exc))


def goal_title(target: str) -> str:
    cleaned = target.strip()
    if cleaned.lower().startswith("become a "):
        cleaned = cleaned[9:]
    elif cleaned.lower().startswith("become an "):
        cleaned = cleaned[10:]
    elif cleaned.lower().startswith("become "):
        cleaned = cleaned[7:]
    return cleaned.title()

