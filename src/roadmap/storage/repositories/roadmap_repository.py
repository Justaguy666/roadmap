"""SQLAlchemy implementation of RoadmapRepository."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from roadmap.domain.entities.learning_resource import LearningResource, Project
from roadmap.domain.entities.roadmap import Milestone, Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.value_objects import Priority, ResourceType, SkillLevel, SkillStatus
from roadmap.storage.models.roadmap_model import (
    LearningResourceModel,
    MilestoneModel,
    ProjectModel,
    RoadmapModel,
    RoadmapPhaseModel,
)
from roadmap.storage.models.skill_model import SkillModel


class SqliteRoadmapRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, roadmap: Roadmap) -> None:
        existing = self._session.get(RoadmapModel, roadmap.id)
        if existing:
            self._session.delete(existing)
            self._session.flush()

        rm = RoadmapModel(
            id=roadmap.id,
            profile_id=roadmap.profile_id,
            title=roadmap.title,
            total_estimated_hours=roadmap.total_estimated_hours,
            total_weeks=roadmap.total_weeks,
            assumptions_json=json.dumps(roadmap.assumptions),
            skipped_skill_names_json=json.dumps(roadmap.skipped_skill_names),
            research_run_id=roadmap.research_run_id,
            generated_at=roadmap.generated_at,
            last_updated_at=roadmap.last_updated_at,
        )
        self._session.add(rm)
        self._session.flush()

        for phase in roadmap.phases:
            for skill in phase.skills:
                existing_skill = self._session.get(SkillModel, skill.id)
                if existing_skill is None:
                    self._session.add(SkillModel(
                        id=skill.id,
                        profile_id=roadmap.profile_id,
                        name=skill.name,
                        category=skill.category,
                        description=skill.description,
                        current_level=skill.current_level.value,
                        target_level=skill.target_level.value,
                        status=skill.status.value,
                        priority=skill.priority.value,
                        market_demand_score=skill.market_demand_score,
                        goal_relevance_score=skill.goal_relevance_score,
                        estimated_hours=skill.estimated_hours,
                        prerequisite_names_json=json.dumps(skill.prerequisite_names),
                        evidence_ids_json=json.dumps(skill.evidence_ids),
                    ))
            self._session.flush()

            skill_ids = [s.id for s in phase.skills]
            pm = RoadmapPhaseModel(
                id=phase.id,
                roadmap_id=roadmap.id,
                phase_number=phase.phase_number,
                name=phase.name,
                objective=phase.objective,
                estimated_weeks=phase.estimated_weeks,
                is_completed=phase.is_completed,
                completed_at=phase.completed_at,
                skill_ids_json=json.dumps(skill_ids),
            )
            self._session.add(pm)
            self._session.flush()
            for milestone in phase.milestones:
                mm = MilestoneModel(
                    id=milestone.id,
                    phase_id=phase.id,
                    name=milestone.name,
                    description=milestone.description,
                    exit_criteria_json=json.dumps(milestone.exit_criteria),
                    estimated_weeks=milestone.estimated_weeks,
                    is_achieved=milestone.is_achieved,
                    achieved_at=milestone.achieved_at,
                )
                self._session.add(mm)
            for resource in phase.resources:
                rmodel = LearningResourceModel(
                    id=resource.id,
                    phase_id=phase.id,
                    title=resource.title,
                    resource_type=resource.resource_type.value,
                    url=resource.url,
                    provider=resource.provider,
                    difficulty=resource.difficulty.value,
                    estimated_hours=resource.estimated_hours,
                    cost=resource.cost,
                    is_free=resource.is_free,
                    freshness_year=resource.freshness_year,
                    quality_score=resource.quality_score,
                    associated_skill_names_json=json.dumps(resource.associated_skill_names),
                    source_id=resource.source_id,
                )
                self._session.add(rmodel)
            for project in phase.projects:
                pmodel = ProjectModel(
                    id=project.id,
                    phase_id=phase.id,
                    name=project.name,
                    description=project.description,
                    required_skill_names_json=json.dumps(project.required_skill_names),
                    difficulty=project.difficulty.value,
                    expected_outcome=project.expected_outcome,
                    portfolio_value=project.portfolio_value,
                    estimated_hours=project.estimated_hours,
                )
                self._session.add(pmodel)

    def load_latest(self, profile_id: str) -> Roadmap | None:
        rm = (
            self._session.query(RoadmapModel)
            .filter(RoadmapModel.profile_id == profile_id)
            .order_by(RoadmapModel.generated_at.desc())
            .first()
        )
        if rm is None:
            return None
        return self._to_entity(rm)

    def load_all(self, profile_id: str) -> list[Roadmap]:
        models = (
            self._session.query(RoadmapModel)
            .filter(RoadmapModel.profile_id == profile_id)
            .order_by(RoadmapModel.generated_at.desc())
            .all()
        )
        return [self._to_entity(m) for m in models]

    def delete(self, roadmap_id: str) -> None:
        rm = self._session.get(RoadmapModel, roadmap_id)
        if rm:
            self._session.delete(rm)

    def _to_entity(self, rm: RoadmapModel) -> Roadmap:
        phases: list[RoadmapPhase] = []
        phase_models = (
            self._session.query(RoadmapPhaseModel)
            .filter(RoadmapPhaseModel.roadmap_id == rm.id)
            .order_by(RoadmapPhaseModel.phase_number)
            .all()
        )
        for pm in phase_models:
            skill_ids: list[str] = json.loads(pm.skill_ids_json)
            skills = [
                self._skill_to_entity(sm)
                for sid in skill_ids
                if (sm := self._session.get(SkillModel, sid)) is not None
            ]
            milestones = [
                Milestone(
                    id=mm.id,
                    phase_id=mm.phase_id,
                    name=mm.name,
                    description=mm.description,
                    exit_criteria=json.loads(mm.exit_criteria_json),
                    estimated_weeks=mm.estimated_weeks,
                    is_achieved=mm.is_achieved,
                    achieved_at=mm.achieved_at,
                )
                for mm in self._session.query(MilestoneModel)
                .filter(MilestoneModel.phase_id == pm.id)
                .all()
            ]
            resources = [
                LearningResource(
                    id=r.id,
                    phase_id=r.phase_id,
                    title=r.title,
                    resource_type=ResourceType(r.resource_type),
                    url=r.url,
                    provider=r.provider,
                    difficulty=SkillLevel(r.difficulty),
                    estimated_hours=r.estimated_hours,
                    cost=r.cost,
                    is_free=r.is_free,
                    freshness_year=r.freshness_year,
                    quality_score=r.quality_score,
                    associated_skill_names=json.loads(r.associated_skill_names_json),
                    source_id=r.source_id,
                )
                for r in self._session.query(LearningResourceModel)
                .filter(LearningResourceModel.phase_id == pm.id)
                .all()
            ]
            projects = [
                Project(
                    id=p.id,
                    phase_id=p.phase_id,
                    name=p.name,
                    description=p.description,
                    required_skill_names=json.loads(p.required_skill_names_json),
                    difficulty=SkillLevel(p.difficulty),
                    expected_outcome=p.expected_outcome,
                    portfolio_value=p.portfolio_value,
                    estimated_hours=p.estimated_hours,
                )
                for p in self._session.query(ProjectModel)
                .filter(ProjectModel.phase_id == pm.id)
                .all()
            ]
            phases.append(RoadmapPhase(
                id=pm.id,
                roadmap_id=rm.id,
                phase_number=pm.phase_number,
                name=pm.name,
                objective=pm.objective,
                skills=skills,
                resources=resources,
                projects=projects,
                milestones=milestones,
                estimated_weeks=pm.estimated_weeks,
                is_completed=pm.is_completed,
                completed_at=pm.completed_at,
            ))
        return Roadmap(
            id=rm.id,
            profile_id=rm.profile_id,
            title=rm.title,
            phases=phases,
            total_estimated_hours=rm.total_estimated_hours,
            total_weeks=rm.total_weeks,
            assumptions=json.loads(rm.assumptions_json),
            skipped_skill_names=json.loads(rm.skipped_skill_names_json),
            research_run_id=rm.research_run_id,
            generated_at=rm.generated_at,
            last_updated_at=rm.last_updated_at,
        )

    def _skill_to_entity(self, m: SkillModel) -> Skill:
        return Skill(
            id=m.id,
            profile_id=m.profile_id,
            name=m.name,
            category=m.category,
            description=m.description,
            current_level=SkillLevel(m.current_level),
            target_level=SkillLevel(m.target_level),
            status=SkillStatus(m.status),
            priority=Priority(m.priority),
            market_demand_score=m.market_demand_score,
            goal_relevance_score=m.goal_relevance_score,
            estimated_hours=m.estimated_hours,
            prerequisite_names=json.loads(m.prerequisite_names_json),
            evidence_ids=json.loads(m.evidence_ids_json) if hasattr(m, "evidence_ids_json") and m.evidence_ids_json else [],
        )
