"""Use case: UpdateProgressUseCase.

Records or updates progress on a specific skill in a user's roadmap,
maintains hours logged, calculates unlocked skills, updates phase/roadmap metrics,
and evaluates current progress deviations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from roadmap.domain.entities.adaptation import DeviationReport
from roadmap.domain.entities.progress_record import ProgressRecord, ProgressStatus
from roadmap.domain.entities.skill import Skill
from roadmap.domain.services.deviation_detector import DeviationDetector
from roadmap.domain.services.progress_tracker import ProgressTracker
from roadmap.domain.value_objects import SkillStatus
from roadmap.shared.ids import new_id
from roadmap.storage.repositories.feedback_repository import SqliteFeedbackRepository
from roadmap.storage.repositories.progress_repository import SqliteProgressRepository
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository


@dataclass
class ProgressUpdateResult:
    """Detailed result of updating skill progress."""

    skill: Skill
    record: ProgressRecord
    overall_percentage: float
    unlocked_skills: list[str]
    deviation_report: DeviationReport


class UpdateProgressUseCase:
    def __init__(
        self,
        roadmap_repo: SqliteRoadmapRepository,
        progress_repo: SqliteProgressRepository,
        feedback_repo: SqliteFeedbackRepository | None = None,
        tracker: ProgressTracker | None = None,
        deviation_detector: DeviationDetector | None = None,
    ) -> None:
        self.roadmap_repo = roadmap_repo
        self.progress_repo = progress_repo
        self.feedback_repo = feedback_repo
        self.tracker = tracker or ProgressTracker()
        self.deviation_detector = deviation_detector or DeviationDetector()

    def execute(
        self,
        profile_id: str,
        skill_identifier: str,  # skill id or skill name
        percentage: float,
        actual_hours: float | None = None,
        status: ProgressStatus | None = None,
        notes: str = "",
    ) -> ProgressUpdateResult:
        """
        Record updated progress for a skill, recompute metrics, and check deviation.
        """
        roadmap = self.roadmap_repo.load_latest(profile_id)
        if not roadmap:
            raise ValueError("No active roadmap found for user.")

        # Find target skill
        target_skill: Skill | None = None
        target_phase_id: str | None = None
        for phase in roadmap.phases:
            for skill in phase.skills:
                if skill.id == skill_identifier or skill.name.lower() == skill_identifier.lower():
                    target_skill = skill
                    target_phase_id = phase.id
                    break
            if target_skill:
                break

        if not target_skill:
            raise ValueError(f"Skill '{skill_identifier}' not found in current roadmap.")

        # Load or create progress record
        existing = self.progress_repo.load_for_skill(profile_id, target_skill.id)
        now = datetime.now(UTC)

        clamped_pct = min(100.0, max(0.0, percentage))
        if existing:
            existing.update_progress(
                percentage=clamped_pct,
                notes=notes,
                actual_hours=actual_hours,
                status=status,
            )
            record = existing
        else:
            rec_status = status
            if rec_status is None:
                if clamped_pct >= 100.0:
                    rec_status = ProgressStatus.COMPLETED
                elif clamped_pct > 0.0:
                    rec_status = ProgressStatus.IN_PROGRESS
                else:
                    rec_status = ProgressStatus.NOT_STARTED

            record = ProgressRecord(
                id=new_id(),
                profile_id=profile_id,
                skill_id=target_skill.id,
                skill_name=target_skill.name,
                phase_id=target_phase_id,
                status=rec_status,
                completion_percentage=clamped_pct,
                planned_hours=target_skill.estimated_hours,
                actual_hours=actual_hours if actual_hours is not None else 0.0,
                started_at=now if rec_status in (ProgressStatus.IN_PROGRESS, ProgressStatus.COMPLETED) else None,
                completed_at=now if clamped_pct >= 100.0 or rec_status == ProgressStatus.COMPLETED else None,
                notes=notes,
                created_at=now,
                updated_at=now,
            )

        self.progress_repo.save(record)

        # Update domain skill entity status
        if record.is_complete:
            target_skill.status = SkillStatus.COMPLETED
            target_skill.current_level = target_skill.target_level
        elif record.completion_percentage > 0.0:
            target_skill.status = SkillStatus.IN_PROGRESS

        # Recompute overall progress
        all_records = self.progress_repo.load_all(profile_id)
        progress_map = {r.skill_id: r.completion_percentage for r in all_records}
        computed = self.tracker.compute_roadmap_progress(roadmap, progress_map)
        overall_pct = computed.get("overall", 0.0)

        # Update phases is_completed if all skills in phase are complete
        for phase in roadmap.phases:
            if phase.skills and all(progress_map.get(s.id, 0.0) >= 100.0 for s in phase.skills):
                phase.is_completed = True
                if phase.completed_at is None:
                    phase.completed_at = now
            elif phase.skills:
                phase.is_completed = False
                phase.completed_at = None

        self.roadmap_repo.save(roadmap)

        # Determine unlocked skills
        # Extract dependencies across all skills
        from roadmap.domain.entities.skill import SkillDependency
        from roadmap.domain.value_objects import DependencyType
        dependencies: list[SkillDependency] = []
        name_to_id = {s.name.lower(): s.id for s in roadmap.all_skills}
        for s in roadmap.all_skills:
            for p_name in s.prerequisite_names:
                p_id = name_to_id.get(p_name.lower())
                if p_id:
                    dependencies.append(
                        SkillDependency(
                            from_skill_id=p_id,
                            to_skill_id=s.id,
                            dependency_type=DependencyType.REQUIRES,
                        )
                    )

        unlocked = self.tracker.determine_unlocked_skills(
            all_skills=roadmap.all_skills,
            dependencies=dependencies,
            progress_map=progress_map,
        )

        # Load feedback if available
        feedbacks = []
        if self.feedback_repo:
            feedbacks = self.feedback_repo.load_for_roadmap(roadmap.id)

        # Analyze deviation
        deviation_report = self.deviation_detector.analyze_deviation(
            roadmap=roadmap,
            progress_records=all_records,
            feedback_records=feedbacks,
        )

        return ProgressUpdateResult(
            skill=target_skill,
            record=record,
            overall_percentage=overall_pct,
            unlocked_skills=unlocked,
            deviation_report=deviation_report,
        )
