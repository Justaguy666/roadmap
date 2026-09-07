"""Use case: RecordFeedbackUseCase.

Records qualitative learner feedback (difficulty, confidence, satisfaction, blockers),
validating scores and tying feedback to the active roadmap and target skill.
"""

from __future__ import annotations

from roadmap.application.ports.repositories import FeedbackRepository, RoadmapRepository
from roadmap.domain.entities.feedback import LearningFeedback
from roadmap.shared.ids import new_id


class RecordFeedbackUseCase:
    def __init__(
        self,
        roadmap_repo: RoadmapRepository,
        feedback_repo: FeedbackRepository,
    ) -> None:
        self.roadmap_repo = roadmap_repo
        self.feedback_repo = feedback_repo

    def execute(
        self,
        profile_id: str,
        difficulty: int = 3,
        confidence: int = 3,
        satisfaction: int = 3,
        skill_identifier: str | None = None,
        blocked_reason: str = "",
        free_text: str = "",
    ) -> LearningFeedback:
        """
        Record learner feedback against the active roadmap.
        """
        roadmap = self.roadmap_repo.load_latest(profile_id)
        if not roadmap:
            raise ValueError("No active roadmap found for user.")

        skill_id: str | None = None
        skill_name = ""
        phase_id: str | None = None

        if skill_identifier:
            for phase in roadmap.phases:
                for skill in phase.skills:
                    if skill.id == skill_identifier or skill.name.lower() == skill_identifier.lower():
                        skill_id = skill.id
                        skill_name = skill.name
                        phase_id = phase.id
                        break
                if skill_id:
                    break

            if not skill_id:
                # Store verbatim name if not matched exactly to a known skill
                skill_name = skill_identifier

        # Clamp 1-5 ratings
        clamped_diff = max(1, min(5, difficulty))
        clamped_conf = max(1, min(5, confidence))
        clamped_sat = max(1, min(5, satisfaction))

        feedback = LearningFeedback(
            id=new_id(),
            profile_id=profile_id,
            roadmap_id=roadmap.id,
            skill_id=skill_id,
            skill_name=skill_name,
            phase_id=phase_id,
            difficulty=clamped_diff,
            confidence=clamped_conf,
            satisfaction=clamped_sat,
            blocked_reason=blocked_reason.strip(),
            free_text=free_text.strip(),
        )

        self.feedback_repo.save(feedback)
        return feedback
