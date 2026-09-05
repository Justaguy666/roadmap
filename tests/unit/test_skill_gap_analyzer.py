"""Unit tests for SkillGapAnalyzer domain service."""

from __future__ import annotations

import pytest

from roadmap.domain.entities.skill import Skill
from roadmap.domain.services.skill_gap_analyzer import SkillGapAnalyzer
from roadmap.domain.value_objects import Priority, SkillLevel, SkillStatus
from roadmap.shared.ids import new_id

PROFILE_ID = "test-profile-001"


def make_skill(
    name: str,
    current: SkillLevel = SkillLevel.MISSING,
    target: SkillLevel = SkillLevel.PROFICIENT,
    priority: Priority = Priority.HIGH,
) -> Skill:
    return Skill(
        id=new_id(),
        profile_id=PROFILE_ID,
        name=name,
        current_level=current,
        target_level=target,
        priority=priority,
    )


class TestSkillGapAnalyzer:
    def setup_method(self) -> None:
        self.analyzer = SkillGapAnalyzer()

    def test_missing_skill_classified_as_missing(self) -> None:
        skill = make_skill("C++", current=SkillLevel.MISSING)
        report = self.analyzer.analyze({}, [skill])
        assert len(report.missing_skills) == 1
        assert report.missing_skills[0].skill_name == "C++"

    def test_completed_skill_classified_correctly(self) -> None:
        skill = make_skill(
            "Python", current=SkillLevel.PROFICIENT, target=SkillLevel.PROFICIENT
        )
        report = self.analyzer.analyze({"python": SkillLevel.PROFICIENT}, [skill])
        assert len(report.completed_skills) == 1
        assert len(report.missing_skills) == 0

    def test_partial_skill_classified_as_partial(self) -> None:
        skill = make_skill(
            "Algorithms", current=SkillLevel.FAMILIAR, target=SkillLevel.MASTERED
        )
        report = self.analyzer.analyze({"algorithms": SkillLevel.FAMILIAR}, [skill])
        assert len(report.partial_skills) == 1
        assert report.partial_skills[0].level_gap == 3  # FAMILIAR→MASTERED = 3 levels

    def test_completion_rate(self) -> None:
        skills = [
            make_skill("A", current=SkillLevel.MISSING, target=SkillLevel.PROFICIENT),
            make_skill("B", current=SkillLevel.PROFICIENT, target=SkillLevel.PROFICIENT),
        ]
        skill_map = {"b": SkillLevel.PROFICIENT}
        report = self.analyzer.analyze(skill_map, skills)
        assert report.completion_rate == pytest.approx(0.5)

    def test_sorted_by_priority(self) -> None:
        skills = [
            make_skill("Low", priority=Priority.LOW),
            make_skill("Critical", priority=Priority.CRITICAL),
            make_skill("High", priority=Priority.HIGH),
        ]
        report = self.analyzer.analyze({}, skills)
        priorities = [g.priority for g in report.missing_skills]
        assert priorities == sorted(priorities, reverse=True)

    def test_build_current_skill_map(self) -> None:
        skill_names = ["C++", "Python", "Git"]
        skill_map = self.analyzer.build_current_skill_map(skill_names)
        assert skill_map["c++"] == SkillLevel.PROFICIENT
        assert skill_map["python"] == SkillLevel.PROFICIENT
        assert "java" not in skill_map

    def test_apply_progress_upgrades_to_mastered(self) -> None:
        skill_map = {"c++": SkillLevel.PROFICIENT}
        updated = self.analyzer.apply_progress(skill_map, ["C++"])
        assert updated["c++"] == SkillLevel.MASTERED

    def test_empty_required_skills(self) -> None:
        report = self.analyzer.analyze({}, [])
        assert report.total_actionable == 0
        assert report.completion_rate == 1.0

    def test_skill_status_for_completed(self) -> None:
        skill = make_skill("A", target=SkillLevel.PROFICIENT)
        status = self.analyzer.skill_status_for(
            skill, {"a": SkillLevel.MASTERED}
        )
        assert status == SkillStatus.COMPLETED

    def test_skill_status_for_in_progress(self) -> None:
        skill = make_skill("A", target=SkillLevel.MASTERED)
        status = self.analyzer.skill_status_for(
            skill, {"a": SkillLevel.FAMILIAR}
        )
        assert status == SkillStatus.IN_PROGRESS
