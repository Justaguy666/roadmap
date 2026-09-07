"""SQLAlchemy implementation of AdaptationRepository."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from roadmap.domain.entities.adaptation import RoadmapAdaptation
from roadmap.storage.models.adaptation_model import RoadmapAdaptationModel


class SqliteAdaptationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, adaptation: RoadmapAdaptation) -> None:
        model = RoadmapAdaptationModel(
            id=adaptation.id,
            profile_id=adaptation.profile_id,
            previous_roadmap_id=adaptation.previous_roadmap_id,
            new_roadmap_id=adaptation.new_roadmap_id,
            previous_version=adaptation.previous_version,
            new_version=adaptation.new_version,
            trigger_reason=adaptation.trigger_reason,
            deviation_summary_json=json.dumps(adaptation.deviation_summary),
            user_feedback_summary_json=json.dumps(adaptation.user_feedback_summary),
            changes_summary_json=json.dumps(adaptation.changes_summary),
            accepted=adaptation.accepted,
            created_at=adaptation.created_at,
        )
        self._session.add(model)

    def load_for_profile(self, profile_id: str) -> list[RoadmapAdaptation]:
        models = (
            self._session.query(RoadmapAdaptationModel)
            .filter(RoadmapAdaptationModel.profile_id == profile_id)
            .order_by(RoadmapAdaptationModel.created_at.desc())
            .all()
        )
        return [self._to_entity(m) for m in models]

    def load_by_version(self, profile_id: str, new_version: int) -> RoadmapAdaptation | None:
        model = (
            self._session.query(RoadmapAdaptationModel)
            .filter(
                RoadmapAdaptationModel.profile_id == profile_id,
                RoadmapAdaptationModel.new_version == new_version,
            )
            .first()
        )
        return self._to_entity(model) if model else None

    def get_latest_adaptation(self, profile_id: str) -> RoadmapAdaptation | None:
        model = (
            self._session.query(RoadmapAdaptationModel)
            .filter(RoadmapAdaptationModel.profile_id == profile_id)
            .order_by(RoadmapAdaptationModel.created_at.desc())
            .first()
        )
        return self._to_entity(model) if model else None

    def _to_entity(self, m: RoadmapAdaptationModel) -> RoadmapAdaptation:
        try:
            dev = json.loads(m.deviation_summary_json) if m.deviation_summary_json else {}
        except Exception:
            dev = {}
        try:
            fb = json.loads(m.user_feedback_summary_json) if m.user_feedback_summary_json else {}
        except Exception:
            fb = {}
        try:
            ch = json.loads(m.changes_summary_json) if m.changes_summary_json else {}
        except Exception:
            ch = {}

        return RoadmapAdaptation(
            id=m.id,
            profile_id=m.profile_id,
            previous_roadmap_id=m.previous_roadmap_id,
            new_roadmap_id=m.new_roadmap_id,
            previous_version=m.previous_version,
            new_version=m.new_version,
            trigger_reason=m.trigger_reason,
            deviation_summary=dev,
            user_feedback_summary=fb,
            changes_summary=ch,
            accepted=m.accepted,
            created_at=m.created_at,
        )
