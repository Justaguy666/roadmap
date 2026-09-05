"""
Domain service: TimeEstimator.

Estimates realistic learning time for skills, phases, and full roadmaps,
taking the user's available study hours into account.

This is deterministic arithmetic — no LLM, no external deps.
"""

from __future__ import annotations

from dataclasses import dataclass

from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.value_objects import SkillLevel

# Approximate hours to cover one "level gap" for a skill
# These are starting estimates, refined by LLM in later MVPs.
HOURS_PER_LEVEL_GAP: dict[tuple[SkillLevel, SkillLevel], float] = {
    (SkillLevel.MISSING, SkillLevel.FAMILIAR): 20,
    (SkillLevel.MISSING, SkillLevel.LEARNING): 50,
    (SkillLevel.MISSING, SkillLevel.PROFICIENT): 120,
    (SkillLevel.MISSING, SkillLevel.MASTERED): 250,
    (SkillLevel.FAMILIAR, SkillLevel.LEARNING): 30,
    (SkillLevel.FAMILIAR, SkillLevel.PROFICIENT): 80,
    (SkillLevel.FAMILIAR, SkillLevel.MASTERED): 180,
    (SkillLevel.LEARNING, SkillLevel.PROFICIENT): 50,
    (SkillLevel.LEARNING, SkillLevel.MASTERED): 130,
    (SkillLevel.PROFICIENT, SkillLevel.MASTERED): 80,
}

# Complexity multipliers by category
CATEGORY_MULTIPLIERS: dict[str, float] = {
    "mathematics": 1.4,
    "algorithms": 1.3,
    "computer graphics": 1.5,
    "machine learning": 1.4,
    "game engine": 1.3,
    "programming": 1.0,
    "tools": 0.7,
    "version control": 0.6,
    "general": 1.0,
}


@dataclass(frozen=True)
class TimeEstimate:
    """Result of a time estimation calculation."""

    estimated_hours: float
    weeks_at_rate: float           # given study_hours_per_week
    is_within_deadline: bool
    slack_weeks: float             # positive = comfortable, negative = tight


class TimeEstimator:
    """Estimates realistic learning times for skills and roadmap phases."""

    def estimate_skill_hours(self, skill: Skill) -> float:
        """
        Estimate hours needed to bring a skill from current_level to target_level.

        If the skill already has an estimated_hours set, use that.
        Otherwise, use the lookup table + category multiplier.
        """
        if skill.estimated_hours > 0:
            return skill.estimated_hours

        if skill.current_level >= skill.target_level:
            return 0.0

        key = (skill.current_level, skill.target_level)
        base_hours = HOURS_PER_LEVEL_GAP.get(key, 80.0)  # default 80h if key missing

        multiplier = CATEGORY_MULTIPLIERS.get(skill.category.lower(), 1.0)
        return round(base_hours * multiplier, 1)

    def estimate_phase_weeks(
        self,
        phase: RoadmapPhase,
        study_hours_per_week: float,
    ) -> float:
        """Estimate weeks to complete a phase given available study time."""
        if study_hours_per_week <= 0:
            return 999.0
        total_hours = sum(
            self.estimate_skill_hours(s) for s in phase.skills
        )
        total_hours += sum(r.estimated_hours for r in phase.resources)
        total_hours += sum(p.estimated_hours for p in phase.projects)
        return round(total_hours / study_hours_per_week, 1)

    def estimate_roadmap(
        self,
        roadmap: Roadmap,
        study_hours_per_week: float,
        deadline_weeks: float,
    ) -> TimeEstimate:
        """Estimate total roadmap completion time and check deadline feasibility."""
        total_hours = sum(
            self.estimate_skill_hours(s)
            for phase in roadmap.phases
            for s in phase.skills
        )
        total_hours += sum(
            r.estimated_hours
            for phase in roadmap.phases
            for r in phase.resources
        )
        total_hours += sum(
            p.estimated_hours
            for phase in roadmap.phases
            for p in phase.projects
        )

        weeks = total_hours / max(study_hours_per_week, 0.1)
        slack = deadline_weeks - weeks

        return TimeEstimate(
            estimated_hours=round(total_hours, 1),
            weeks_at_rate=round(weeks, 1),
            is_within_deadline=weeks <= deadline_weeks,
            slack_weeks=round(slack, 1),
        )

    def fill_skill_estimates(self, skills: list[Skill]) -> list[Skill]:
        """
        Return skills with estimated_hours populated from lookup table
        if they don't already have estimates.
        """
        for skill in skills:
            if skill.estimated_hours == 0.0:
                skill.estimated_hours = self.estimate_skill_hours(skill)
        return skills
