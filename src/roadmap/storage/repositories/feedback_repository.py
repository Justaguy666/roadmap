"""SQLAlchemy implementation of FeedbackRepository."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from roadmap.domain.entities.feedback import LearningFeedback
from roadmap.storage.models.feedback_model import LearningFeedbackModel


class SqliteFeedbackRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, feedback: LearningFeedback) -> None:
        model = LearningFeedbackModel(
            id=feedback.id,
            profile_id=feedback.profile_id,
            roadmap_id=feedback.roadmap_id,
            skill_id=feedback.skill_id,
            skill_name=feedback.skill_name,
            phase_id=feedback.phase_id,
            difficulty=feedback.difficulty,
            confidence=feedback.confidence,
            satisfaction=feedback.satisfaction,
            blocked_reason=feedback.blocked_reason,
            free_text=feedback.free_text,
            metadata_json=json.dumps(feedback.metadata_json),
            created_at=feedback.created_at,
        )
        self._session.add(model)

    def load_for_roadmap(self, roadmap_id: str) -> list[LearningFeedback]:
        models = (
            self._session.query(LearningFeedbackModel)
            .filter(LearningFeedbackModel.roadmap_id == roadmap_id)
            .order_by(LearningFeedbackModel.created_at.desc())
            .all()
        )
        return [self._to_entity(m) for m in models]

    def load_for_skill(self, roadmap_id: str, skill_id: str) -> list[LearningFeedback]:
        models = (
            self._session.query(LearningFeedbackModel)
            .filter(
                LearningFeedbackModel.roadmap_id == roadmap_id,
                LearningFeedbackModel.skill_id == skill_id,
            )
            .order_by(LearningFeedbackModel.created_at.desc())
            .all()
        )
        return [self._to_entity(m) for m in models]

    def _to_entity(self, m: LearningFeedbackModel) -> LearningFeedback:
        try:
            meta = json.loads(m.metadata_json) if m.metadata_json else {}
        except Exception:
            meta = {}

        return LearningFeedback(
            id=m.id,
            profile_id=m.profile_id,
            roadmap_id=m.roadmap_id,
            skill_id=m.skill_id,
            skill_name=m.skill_name,
            phase_id=m.phase_id,
            difficulty=m.difficulty,
            confidence=m.confidence,
            satisfaction=m.satisfaction,
            blocked_reason=m.blocked_reason,
            free_text=m.free_text,
            metadata_json=meta,
            created_at=m.created_at,
        )
