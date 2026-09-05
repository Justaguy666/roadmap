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

from roadmap.agents.prompts.roadmap_generation import (
    ROADMAP_GENERATION_SYSTEM_PROMPT,
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
from roadmap.application.ports.llm_provider import LLMMessage, LLMProvider
from roadmap.application.ports.repositories import (
    ProfileRepository,
    RoadmapRepository,
    SkillRepository,
)
from roadmap.application.use_cases.analyze_goal import AnalyzeGoalUseCase
from roadmap.domain.entities.learning_resource import LearningResource, Project
from roadmap.domain.entities.roadmap import Milestone, Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill, SkillDependency
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import RoadmapValidationError
from roadmap.domain.services.priority_calculator import PriorityCalculator
from roadmap.domain.services.roadmap_validator import RoadmapValidator, ValidationResult
from roadmap.domain.services.skill_gap_analyzer import SkillGapAnalyzer
from roadmap.domain.value_objects import DependencyType, SkillStatus
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class GenerateRoadmapUseCase:
    """
    Orchestrates the creation and validation of an evidence-backed learning roadmap.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        profile_repo: ProfileRepository,
        roadmap_repo: RoadmapRepository,
        skill_repo: SkillRepository,
        max_retries: int = 3,
    ) -> None:
        self.llm_provider = llm_provider
        self.profile_repo = profile_repo
        self.roadmap_repo = roadmap_repo
        self.skill_repo = skill_repo
        self.max_retries = max_retries

        self.goal_analyzer = AnalyzeGoalUseCase(llm_provider)
        self.gap_analyzer = SkillGapAnalyzer()
        self.priority_calculator = PriorityCalculator()
        self.validator = RoadmapValidator()

    def execute(
        self,
        profile: UserProfile,
        existing_goal_analysis: GoalAnalysisResult | None = None,
    ) -> tuple[Roadmap, GoalAnalysisResult, SkillGapAnalysisResult, ValidationResult]:
        """
        Execute the full roadmap generation pipeline.
        """
        start_time = time.perf_counter()
        logger.info("Initiating roadmap generation pipeline", profile_id=profile.id)

        # 1. Goal Analysis (or reuse precomputed)
        if existing_goal_analysis is not None:
            goal_analysis = existing_goal_analysis
            logger.info("Using existing goal analysis result")
        else:
            goal_analysis = self.goal_analyzer.execute(profile)

        # 2. Deterministic Skill Gap Analysis
        skill_gaps = self._compute_skill_gaps(profile, goal_analysis)

        # 3. LLM Roadmap Generation with Bounded Retry / Repair
        draft_result, roadmap, validation_result = self._generate_and_validate(
            profile=profile,
            goal_analysis=goal_analysis,
            skill_gaps=skill_gaps,
        )

        # 4. Final Validation Check
        if not validation_result.is_valid:
            error_messages = [e.message for e in validation_result.errors]
            logger.error(
                "Roadmap generation failed validation after all retries",
                errors=error_messages,
            )
            raise RoadmapValidationError(error_messages)

        # 5. Persist the validated Roadmap and Skills
        self.roadmap_repo.save(roadmap)
        self.skill_repo.save_skills(roadmap.all_skills)

        # Save dependencies
        dependencies = self._extract_dependencies(roadmap)
        if dependencies:
            self.skill_repo.save_dependencies(dependencies)

        total_duration = time.perf_counter() - start_time
        logger.info(
            "Roadmap generation pipeline completed and persisted",
            roadmap_id=roadmap.id,
            total_phases=len(roadmap.phases),
            total_skills=len(roadmap.all_skills),
            total_weeks=roadmap.total_weeks,
            duration_seconds=round(total_duration, 2),
        )

        return roadmap, goal_analysis, skill_gaps, validation_result

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
    ) -> Roadmap:
        """
        Convert structured RoadmapGenerationResult into a domain Roadmap entity.
        """
        roadmap_id = new_id()
        domain_phases: list[RoadmapPhase] = []

        for phase_idx, pd in enumerate(draft.phases, start=1):
            phase_id = new_id()

            # Map skills
            skills = [
                Skill(
                    id=new_id(),
                    profile_id=profile.id,
                    name=sd.name,
                    category=sd.category,
                    target_level=sd.target_level,
                    priority=sd.priority,
                    estimated_hours=sd.estimated_hours,
                    prerequisite_names=sd.prerequisites,
                    status=SkillStatus.PENDING,
                )
                for sd in pd.skills
            ]

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
            phases=domain_phases,
            total_weeks=total_weeks,
            assumptions=draft.assumptions,
        )
        roadmap.recalculate_totals()
        return roadmap

    def _extract_dependencies(self, roadmap: Roadmap) -> list[SkillDependency]:
        """
        Extract SkillDependency edges from prerequisite_names.
        """
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
                        dependency_type=DependencyType.REQUIRES,
                        source="llm_generated",
                    ))
        return deps


def goal_title(target: str) -> str:
    cleaned = target.strip()
    if cleaned.lower().startswith("become a "):
        cleaned = cleaned[9:]
    elif cleaned.lower().startswith("become an "):
        cleaned = cleaned[10:]
    elif cleaned.lower().startswith("become "):
        cleaned = cleaned[7:]
    return cleaned.title()
