"""
Domain service: ProgressTracker.

Manages skill completion state, unlocks dependent skills when prerequisites
are met, and recalculates roadmap progress metrics.

This is fully deterministic — no LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from roadmap.domain.entities.progress_record import ProgressRecord
from roadmap.domain.entities.roadmap import Roadmap
from roadmap.domain.entities.skill import Skill, SkillDependency
from roadmap.domain.value_objects import SkillLevel, SkillStatus
from roadmap.shared.ids import new_id


@dataclass
class ProgressUpdate:
    """Result of a progress update operation."""

    updated_skill_name: str
    new_percentage: float
    newly_completed: bool
    unlocked_skill_names: list[str] = field(default_factory=list)
    progress_record: ProgressRecord | None = None


class ProgressTracker:
    """
    Tracks user progress and determines which skills are unlocked.

    Skill unlock logic:
      A skill becomes available when ALL hard prerequisite skills
      (DependencyType.REQUIRES) are completed (>= 80% progress).
    """

    COMPLETION_THRESHOLD = 80.0  # percentage to consider a skill "done"

    def update_skill_progress(
        self,
        profile_id: str,
        skill: Skill,
        percentage: float,
        notes: str = "",
        existing_record: ProgressRecord | None = None,
    ) -> ProgressRecord:
        """Create or update a progress record for a skill."""
        if existing_record is not None:
            existing_record.update_progress(percentage, notes)
            return existing_record

        record = ProgressRecord(
            id=new_id(),
            profile_id=profile_id,
            skill_id=skill.id,
            skill_name=skill.name,
            completion_percentage=min(100.0, max(0.0, percentage)),
            notes=notes,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        if record.is_complete:
            record.completed_at = datetime.now(timezone.utc)
        return record

    def mark_skill_complete(
        self,
        profile_id: str,
        skill: Skill,
        notes: str = "",
        existing_record: ProgressRecord | None = None,
    ) -> ProgressUpdate:
        """Mark a skill as 100% complete and return the update result."""
        record = self.update_skill_progress(
            profile_id, skill, 100.0, notes, existing_record
        )
        skill.status = SkillStatus.COMPLETED
        skill.current_level = skill.target_level

        return ProgressUpdate(
            updated_skill_name=skill.name,
            new_percentage=100.0,
            newly_completed=True,
            progress_record=record,
        )

    def determine_unlocked_skills(
        self,
        all_skills: list[Skill],
        dependencies: list[SkillDependency],
        progress_map: dict[str, float],   # skill_id → completion %
    ) -> list[str]:
        """
        Return names of skills that are now unlocked (prerequisites met).

        A skill is unlocked if all REQUIRES dependencies are >= COMPLETION_THRESHOLD.
        Skills with no prerequisites are always unlocked.
        """
        # Build reverse adjacency: skill_id → list of prerequisite skill_ids
        prereq_map: dict[str, list[str]] = {}
        for dep in dependencies:
            from roadmap.domain.value_objects import DependencyType
            if dep.dependency_type == DependencyType.REQUIRES:
                prereq_map.setdefault(dep.to_skill_id, []).append(dep.from_skill_id)

        unlocked: list[str] = []
        for skill in all_skills:
            if skill.status in (SkillStatus.COMPLETED, SkillStatus.IN_PROGRESS):
                continue  # already active
            prereqs = prereq_map.get(skill.id, [])
            if not prereqs:
                unlocked.append(skill.name)
                continue
            if all(
                progress_map.get(pid, 0.0) >= self.COMPLETION_THRESHOLD
                for pid in prereqs
            ):
                unlocked.append(skill.name)

        return unlocked

    def compute_roadmap_progress(
        self,
        roadmap: Roadmap,
        progress_map: dict[str, float],   # skill_id → completion %
    ) -> dict[str, float]:
        """
        Compute progress for each phase and overall.

        Returns dict with keys:
          - "overall"
          - "phase_1", "phase_2", ...
        """
        result: dict[str, float] = {}

        total_skills = 0
        total_weighted_progress = 0.0

        for phase in roadmap.phases:
            phase_skills = phase.skills
            if not phase_skills:
                result[f"phase_{phase.phase_number}"] = 0.0
                continue

            phase_progress = sum(
                progress_map.get(s.id, 0.0) for s in phase_skills
            )
            phase_avg = phase_progress / len(phase_skills)
            result[f"phase_{phase.phase_number}"] = round(phase_avg, 1)

            total_weighted_progress += phase_progress
            total_skills += len(phase_skills)

        result["overall"] = (
            round(total_weighted_progress / total_skills, 1) if total_skills > 0 else 0.0
        )
        return result

    def get_current_level_from_progress(
        self, skill: Skill, completion_pct: float
    ) -> SkillLevel:
        """
        Map a completion percentage to a SkillLevel.

        0–20%:  MISSING
        20–40%: FAMILIAR
        40–70%: LEARNING
        70–90%: PROFICIENT
        90–100%: MASTERED
        """
        if completion_pct < 20:
            return SkillLevel.MISSING
        if completion_pct < 40:
            return SkillLevel.FAMILIAR
        if completion_pct < 70:
            return SkillLevel.LEARNING
        if completion_pct < 90:
            return SkillLevel.PROFICIENT
        return SkillLevel.MASTERED

