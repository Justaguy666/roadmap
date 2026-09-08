"""
SQLAlchemy implementation of ProfileRepository.

Converts between domain entities and ORM models.
The domain entity never imports from this module.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from roadmap.domain.entities.user import LEGACY_LOCAL_USER_EMAIL, LEGACY_LOCAL_USER_ID
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects import BudgetPreference, SkillLevel
from roadmap.storage.models.user_model import UserModel
from roadmap.storage.models.user_profile_model import UserProfileModel


class SqliteProfileRepository:
    """SQLite/PostgreSQL-backed profile repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _ensure_legacy_user(self) -> str:
        """Guarantee the deterministic legacy user exists for single-user/CLI compatibility."""
        legacy_user = self._session.get(UserModel, LEGACY_LOCAL_USER_ID)
        if legacy_user is None:
            now = datetime.now(UTC)
            legacy_user = UserModel(
                id=LEGACY_LOCAL_USER_ID,
                email=LEGACY_LOCAL_USER_EMAIL,
                password_hash="legacy_local_placeholder_hash",
                status="active",
                created_at=now,
                updated_at=now,
            )
            self._session.add(legacy_user)
            self._session.flush()
        return LEGACY_LOCAL_USER_ID

    def save(self, profile: UserProfile) -> None:
        if not profile.user_id:
            profile.user_id = self._ensure_legacy_user()

        existing = self._session.get(UserProfileModel, profile.id)
        if existing is None:
            model = self._to_model(profile)
            self._session.add(model)
        else:
            self._update_model(existing, profile)

    def load(self) -> UserProfile | None:
        """Load the first (and only) profile — single-user MVP / CLI compatibility."""
        model = self._session.query(UserProfileModel).first()
        if model is None:
            return None
        return self._to_entity(model)

    def load_by_id(self, profile_id: str) -> UserProfile | None:
        """Load profile by unique ID."""
        model = self._session.get(UserProfileModel, profile_id)
        if model is None:
            return None
        return self._to_entity(model)

    def load_by_user_id(self, user_id: str) -> list[UserProfile]:
        """Load all profiles belonging to a user."""
        models = (
            self._session.query(UserProfileModel)
            .filter(UserProfileModel.user_id == user_id)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def load_for_user(self, user_id: str, profile_id: str) -> UserProfile | None:
        """Load specific profile belonging to a user."""
        model = (
            self._session.query(UserProfileModel)
            .filter(UserProfileModel.user_id == user_id, UserProfileModel.id == profile_id)
            .first()
        )
        if model is None:
            return None
        return self._to_entity(model)

    def delete(self, profile_id: str | None = None) -> None:
        if profile_id:
            self._session.query(UserProfileModel).filter(UserProfileModel.id == profile_id).delete()
        else:
            self._session.query(UserProfileModel).delete()

    def exists(self) -> bool:
        return self._session.query(UserProfileModel).count() > 0

    def exists_for_user(self, user_id: str) -> bool:
        return (
            self._session.query(UserProfileModel)
            .filter(UserProfileModel.user_id == user_id)
            .count()
            > 0
        )

    # ── Mapping helpers ───────────────────────────────────────────────────

    def _to_model(self, p: UserProfile) -> UserProfileModel:
        user_id = p.user_id or self._ensure_legacy_user()
        m = UserProfileModel(
            id=p.id,
            user_id=user_id,
            name=p.name,
            target_goal=p.target_goal,
            target_role=p.target_role,
            current_level=p.current_level.value,
            current_skills_json=json.dumps(p.current_skills),
            programming_languages_json=json.dumps(p.programming_languages),
            previous_experience=p.previous_experience,
            completed_projects_json=json.dumps(p.completed_projects),
            preferred_technologies_json=json.dumps(p.preferred_technologies),
            preferred_industry=p.preferred_industry,
            target_markets_json=json.dumps(p.target_markets),
            learning_preferences_json=json.dumps(p.learning_preferences),
            budget=p.budget.value,
            constraints_json=json.dumps(p.constraints),
            study_hours_per_day=p.study_hours_per_day,
            deadline_months=p.deadline_months,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        return m

    def _update_model(self, m: UserProfileModel, p: UserProfile) -> None:
        if p.user_id:
            m.user_id = p.user_id
        elif not m.user_id:
            m.user_id = self._ensure_legacy_user()
        m.name = p.name
        m.target_goal = p.target_goal
        m.target_role = p.target_role
        m.current_level = p.current_level.value
        m.current_skills_json = json.dumps(p.current_skills)
        m.programming_languages_json = json.dumps(p.programming_languages)
        m.previous_experience = p.previous_experience
        m.completed_projects_json = json.dumps(p.completed_projects)
        m.preferred_technologies_json = json.dumps(p.preferred_technologies)
        m.preferred_industry = p.preferred_industry
        m.target_markets_json = json.dumps(p.target_markets)
        m.learning_preferences_json = json.dumps(p.learning_preferences)
        m.budget = p.budget.value
        m.constraints_json = json.dumps(p.constraints)
        m.study_hours_per_day = p.study_hours_per_day
        m.deadline_months = p.deadline_months
        m.updated_at = p.updated_at

    def _to_entity(self, m: UserProfileModel) -> UserProfile:
        return UserProfile(
            id=m.id,
            user_id=m.user_id or "",
            name=m.name,
            target_goal=m.target_goal,
            target_role=m.target_role,
            current_level=SkillLevel(m.current_level),
            current_skills=json.loads(m.current_skills_json),
            programming_languages=json.loads(m.programming_languages_json),
            previous_experience=m.previous_experience,
            completed_projects=json.loads(m.completed_projects_json),
            preferred_technologies=json.loads(m.preferred_technologies_json),
            preferred_industry=m.preferred_industry,
            target_markets=json.loads(m.target_markets_json),
            learning_preferences=json.loads(m.learning_preferences_json),
            budget=BudgetPreference(m.budget),
            constraints=json.loads(m.constraints_json),
            study_hours_per_day=m.study_hours_per_day,
            deadline_months=m.deadline_months,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

