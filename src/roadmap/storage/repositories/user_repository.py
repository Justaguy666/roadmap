"""
SQLAlchemy implementation of UserRepository.

Converts between User domain entities and UserModel ORM records.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from roadmap.domain.entities.user import User
from roadmap.storage.models.user_model import UserModel


class SqliteUserRepository:
    """SQLite/PostgreSQL-backed user repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, user: User) -> None:
        existing = self._session.get(UserModel, user.id)
        if existing is None:
            model = self._to_model(user)
            self._session.add(model)
        else:
            existing.email = user.email
            existing.password_hash = user.password_hash
            existing.status = user.status
            existing.updated_at = user.updated_at

    def get_by_id(self, user_id: str) -> User | None:
        model = self._session.get(UserModel, user_id)
        if model is None:
            return None
        return self._to_entity(model)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        model = self._session.scalars(stmt).first()
        if model is None:
            return None
        return self._to_entity(model)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _to_model(self, u: User) -> UserModel:
        return UserModel(
            id=u.id,
            email=u.email,
            password_hash=u.password_hash,
            status=u.status,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )

    def _to_entity(self, m: UserModel) -> User:
        return User(
            id=m.id,
            email=m.email,
            password_hash=m.password_hash,
            status=m.status,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
