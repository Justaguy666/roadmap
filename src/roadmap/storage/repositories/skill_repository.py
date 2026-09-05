"""SQLAlchemy implementation of SkillRepository."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from roadmap.domain.entities.skill import Skill, SkillDependency
from roadmap.domain.value_objects import DependencyType, Priority, SkillLevel, SkillStatus
from roadmap.storage.models.skill_model import SkillDependencyModel, SkillModel


class SqliteSkillRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_skill(self, skill: Skill) -> None:
        existing = self._session.get(SkillModel, skill.id)
        if existing is None:
            self._session.add(self._to_model(skill))
        else:
            self._update_model(existing, skill)

    def save_skills(self, skills: list[Skill]) -> None:
        for skill in skills:
            self.save_skill(skill)

    def load_skills(self, profile_id: str) -> list[Skill]:
        models = (
            self._session.query(SkillModel)
            .filter(SkillModel.profile_id == profile_id)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def load_skill_by_name(self, profile_id: str, name: str) -> Skill | None:
        model = (
            self._session.query(SkillModel)
            .filter(
                SkillModel.profile_id == profile_id,
                SkillModel.name == name,
            )
            .first()
        )
        return self._to_entity(model) if model else None

    def save_dependency(self, dep: SkillDependency) -> None:
        existing = self._session.get(SkillDependencyModel, dep.id)
        if existing is None:
            self._session.add(SkillDependencyModel(
                id=dep.id,
                from_skill_id=dep.from_skill_id,
                to_skill_id=dep.to_skill_id,
                dependency_type=dep.dependency_type.value,
                confidence=dep.confidence,
                source=dep.source,
                created_at=dep.created_at,
            ))

    def save_dependencies(self, deps: list[SkillDependency]) -> None:
        for dep in deps:
            self.save_dependency(dep)

    def load_dependencies(self, profile_id: str) -> list[SkillDependency]:
        skill_ids = [
            s.id for s in self._session.query(SkillModel.id)
            .filter(SkillModel.profile_id == profile_id)
            .all()
        ]
        if not skill_ids:
            return []
        models = (
            self._session.query(SkillDependencyModel)
            .filter(SkillDependencyModel.from_skill_id.in_(skill_ids))
            .all()
        )
        return [
            SkillDependency(
                id=m.id,
                from_skill_id=m.from_skill_id,
                to_skill_id=m.to_skill_id,
                dependency_type=DependencyType(m.dependency_type),
                confidence=m.confidence,
                source=m.source,
                created_at=m.created_at,
            )
            for m in models
        ]

    def delete_all(self, profile_id: str) -> None:
        skill_ids = [
            s[0] for s in self._session.query(SkillModel.id)
            .filter(SkillModel.profile_id == profile_id)
            .all()
        ]
        if skill_ids:
            self._session.query(SkillDependencyModel).filter(
                SkillDependencyModel.from_skill_id.in_(skill_ids)
            ).delete(synchronize_session=False)
        self._session.query(SkillModel).filter(
            SkillModel.profile_id == profile_id
        ).delete()

    def _to_model(self, s: Skill) -> SkillModel:
        return SkillModel(
            id=s.id,
            profile_id=s.profile_id,
            name=s.name,
            category=s.category,
            description=s.description,
            current_level=s.current_level.value,
            target_level=s.target_level.value,
            status=s.status.value,
            priority=s.priority.value,
            market_demand_score=s.market_demand_score,
            goal_relevance_score=s.goal_relevance_score,
            estimated_hours=s.estimated_hours,
            prerequisite_names_json=json.dumps(s.prerequisite_names),
            evidence_ids_json=json.dumps(s.evidence_ids),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )

    def _update_model(self, m: SkillModel, s: Skill) -> None:
        m.current_level = s.current_level.value
        m.target_level = s.target_level.value
        m.status = s.status.value
        m.priority = s.priority.value
        m.market_demand_score = s.market_demand_score
        m.goal_relevance_score = s.goal_relevance_score
        m.estimated_hours = s.estimated_hours
        m.prerequisite_names_json = json.dumps(s.prerequisite_names)
        m.updated_at = s.updated_at

    def _to_entity(self, m: SkillModel) -> Skill:
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
            evidence_ids=json.loads(m.evidence_ids_json),
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
