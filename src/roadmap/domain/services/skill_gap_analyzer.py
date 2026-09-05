"""
Domain service: SkillGapAnalyzer.

Compares the user's current skills to the goal's required skills
and produces a structured gap analysis.

This service is fully deterministic — it performs no LLM calls.
It depends only on domain entities and value objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from roadmap.domain.entities.skill import Skill
from roadmap.domain.value_objects import Priority, SkillLevel, SkillStatus


@dataclass(frozen=True)
class SkillGap:
    """Represents the gap between current and required proficiency for a skill."""

    skill_name: str
    current_level: SkillLevel
    target_level: SkillLevel
    level_gap: int          # 0 = no gap, 4 = missing → mastered
    priority: Priority
    is_missing: bool        # True if current_level == MISSING

    @property
    def is_critical(self) -> bool:
        return self.priority == Priority.CRITICAL

    @property
    def is_actionable(self) -> bool:
        """True if there is a gap to close."""
        return self.level_gap > 0


@dataclass
class SkillGapReport:
    """Complete skill gap analysis result."""

    missing_skills: list[SkillGap] = field(default_factory=list)
    partial_skills: list[SkillGap] = field(default_factory=list)   # familiar → target
    completed_skills: list[SkillGap] = field(default_factory=list)

    @property
    def all_gaps(self) -> list[SkillGap]:
        return self.missing_skills + self.partial_skills

    @property
    def total_actionable(self) -> int:
        return len(self.all_gaps)

    @property
    def completion_rate(self) -> float:
        total = len(self.missing_skills) + len(self.partial_skills) + len(self.completed_skills)
        if total == 0:
            return 1.0
        return len(self.completed_skills) / total

    def critical_gaps(self) -> list[SkillGap]:
        return [g for g in self.all_gaps if g.is_critical]

    def high_priority_gaps(self) -> list[SkillGap]:
        return [g for g in self.all_gaps if g.priority >= Priority.HIGH]


class SkillGapAnalyzer:
    """
    Analyzes the gap between current user skills and required skills.

    Inputs:
      - current_skill_map: dict[name → SkillLevel] from user profile
      - required_skills: list of Skill domain objects (from goal analysis)

    Output: SkillGapReport
    """

    def analyze(
        self,
        current_skill_map: dict[str, SkillLevel],
        required_skills: list[Skill],
    ) -> SkillGapReport:
        """
        Produce a gap report by comparing current skills to required skills.

        Skills not in *current_skill_map* are treated as MISSING.
        """
        report = SkillGapReport()

        for skill in required_skills:
            current = current_skill_map.get(skill.name.lower(), SkillLevel.MISSING)
            target = skill.target_level
            gap = max(0, target.numeric() - current.numeric())

            skill_gap = SkillGap(
                skill_name=skill.name,
                current_level=current,
                target_level=target,
                level_gap=gap,
                priority=skill.priority,
                is_missing=current == SkillLevel.MISSING,
            )

            if gap == 0:
                report.completed_skills.append(skill_gap)
            elif current == SkillLevel.MISSING:
                report.missing_skills.append(skill_gap)
            else:
                report.partial_skills.append(skill_gap)

        # Sort by priority descending
        report.missing_skills.sort(key=lambda g: g.priority.numeric(), reverse=True)
        report.partial_skills.sort(key=lambda g: g.priority.numeric(), reverse=True)

        return report

    def build_current_skill_map(self, profile_skill_names: list[str]) -> dict[str, SkillLevel]:
        """
        Build a current-skill map from a list of skill name strings.

        Skills mentioned in the profile are assumed PROFICIENT.
        Unrecognized skills remain MISSING (default).

        In MVP-2+, the LLM will assess actual levels per skill.
        """
        return {name.lower(): SkillLevel.PROFICIENT for name in profile_skill_names if name}

    def apply_progress(
        self,
        skill_map: dict[str, SkillLevel],
        completed_skill_names: list[str],
    ) -> dict[str, SkillLevel]:
        """
        Upgrade completed skills to MASTERED in the skill map.
        Returns a new dict (immutable update pattern).
        """
        updated = dict(skill_map)
        for name in completed_skill_names:
            updated[name.lower()] = SkillLevel.MASTERED
        return updated

    def skill_status_for(
        self, skill: Skill, current_skill_map: dict[str, SkillLevel]
    ) -> SkillStatus:
        """Determine the SkillStatus of a single skill given the current map."""
        current = current_skill_map.get(skill.name.lower(), SkillLevel.MISSING)
        if current >= skill.target_level:
            return SkillStatus.COMPLETED
        if current > SkillLevel.MISSING:
            return SkillStatus.IN_PROGRESS
        return SkillStatus.PENDING
