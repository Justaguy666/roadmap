from __future__ import annotations

from sqlalchemy.orm import Session

from roadmap.domain.entities.progress_record import ProgressRecord, ProgressStatus
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
            existing.status = record.status.value
            existing.planned_hours = record.planned_hours
            existing.actual_hours = record.actual_hours
            existing.started_at = record.started_at
            existing.completed_at = record.completed_at
            existing.notes = record.notes
            existing.updated_at = record.updated_at
            if record.phase_id:
                existing.phase_id = record.phase_id

    def load_all(self, profile_id: str) -> list[ProgressRecord]:
        models = (
            self._session.query(ProgressRecordModel)
            .filter(ProgressRecordModel.profile_id == profile_id)
            .order_by(ProgressRecordModel.updated_at.desc())
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
            phase_id=r.phase_id,
            status=r.status.value,
            completion_percentage=r.completion_percentage,
            planned_hours=r.planned_hours,
            actual_hours=r.actual_hours,
            started_at=r.started_at,
            completed_at=r.completed_at,
            notes=r.notes,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    def _to_entity(self, m: ProgressRecordModel) -> ProgressRecord:
        raw_status = getattr(m, "status", "NOT_STARTED")
        try:
            status = ProgressStatus(raw_status)
        except ValueError:
            status = ProgressStatus.NOT_STARTED

        return ProgressRecord(
            id=m.id,
            profile_id=m.profile_id,
            skill_id=m.skill_id,
            skill_name=m.skill_name,
            phase_id=getattr(m, "phase_id", None),
            status=status,
            completion_percentage=m.completion_percentage,
            planned_hours=getattr(m, "planned_hours", 0.0),
            actual_hours=getattr(m, "actual_hours", 0.0),
            started_at=getattr(m, "started_at", None),
            completed_at=m.completed_at,
            notes=m.notes,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
