"""SQLAlchemy implementation of ProgressRepository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from roadmap.domain.entities.progress_record import ProgressRecord
from roadmap.storage.models.progress_model import ProgressRecordModel


class SqliteProgressRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, record: ProgressRecord) -> None:
        existing = self._session.get(ProgressRecordModel, record.id)
        if existing is None:
            self._session.add(self._to_model(record))
        else:
            existing.completion_percentage = record.completion_percentage
            existing.completed_at = record.completed_at
            existing.notes = record.notes
            existing.updated_at = record.updated_at

    def load_all(self, profile_id: str) -> list[ProgressRecord]:
        models = (
            self._session.query(ProgressRecordModel)
            .filter(ProgressRecordModel.profile_id == profile_id)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def load_for_skill(self, profile_id: str, skill_id: str) -> ProgressRecord | None:
        model = (
            self._session.query(ProgressRecordModel)
            .filter(
                ProgressRecordModel.profile_id == profile_id,
                ProgressRecordModel.skill_id == skill_id,
            )
            .order_by(ProgressRecordModel.updated_at.desc())
            .first()
        )
        return self._to_entity(model) if model else None

    def delete_all(self, profile_id: str) -> None:
        self._session.query(ProgressRecordModel).filter(
            ProgressRecordModel.profile_id == profile_id
        ).delete()

    def _to_model(self, r: ProgressRecord) -> ProgressRecordModel:
        return ProgressRecordModel(
            id=r.id,
            profile_id=r.profile_id,
            skill_id=r.skill_id,
            skill_name=r.skill_name,
            completion_percentage=r.completion_percentage,
            completed_at=r.completed_at,
            notes=r.notes,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    def _to_entity(self, m: ProgressRecordModel) -> ProgressRecord:
        return ProgressRecord(
            id=m.id,
            profile_id=m.profile_id,
            skill_id=m.skill_id,
            skill_name=m.skill_name,
            completion_percentage=m.completion_percentage,
            completed_at=m.completed_at,
            notes=m.notes,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
