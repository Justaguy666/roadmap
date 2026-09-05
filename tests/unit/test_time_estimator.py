"""Unit tests for TimeEstimator domain service."""

from __future__ import annotations

import pytest

from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.services.time_estimator import TimeEstimator
from roadmap.domain.value_objects import SkillLevel
from roadmap.shared.ids import new_id


def make_skill(
    current: SkillLevel, target: SkillLevel, category: str = "general", hours: float = 0.0
) -> Skill:
    return Skill(
        id=new_id(),
        profile_id="p1",
        name="Skill",
        current_level=current,
        target_level=target,
        category=category,
        estimated_hours=hours,
    )


class TestTimeEstimator:
    def setup_method(self) -> None:
        self.est = TimeEstimator()

    def test_returns_zero_if_already_at_target(self) -> None:
        skill = make_skill(SkillLevel.PROFICIENT, SkillLevel.PROFICIENT)
        assert self.est.estimate_skill_hours(skill) == 0.0

    def test_returns_provided_hours_if_set(self) -> None:
        skill = make_skill(SkillLevel.MISSING, SkillLevel.MASTERED, hours=300.0)
        assert self.est.estimate_skill_hours(skill) == 300.0

    def test_missing_to_familiar_reasonable_estimate(self) -> None:
        skill = make_skill(SkillLevel.MISSING, SkillLevel.FAMILIAR)
        hours = self.est.estimate_skill_hours(skill)
        assert 10 <= hours <= 60

    def test_mathematics_multiplier_applied(self) -> None:
        skill_gen = make_skill(SkillLevel.MISSING, SkillLevel.PROFICIENT, "general")
        skill_math = make_skill(SkillLevel.MISSING, SkillLevel.PROFICIENT, "mathematics")
        assert self.est.estimate_skill_hours(skill_math) > self.est.estimate_skill_hours(skill_gen)

    def test_tools_multiplier_is_lower(self) -> None:
        skill_tools = make_skill(SkillLevel.MISSING, SkillLevel.PROFICIENT, "tools")
        skill_gen = make_skill(SkillLevel.MISSING, SkillLevel.PROFICIENT, "general")
        assert self.est.estimate_skill_hours(skill_tools) < self.est.estimate_skill_hours(skill_gen)

    def test_estimate_phase_weeks(self) -> None:
        phase = RoadmapPhase(
            id=new_id(), roadmap_id="r1", phase_number=1, name="Test",
            skills=[make_skill(SkillLevel.MISSING, SkillLevel.FAMILIAR, hours=20.0)],
        )
        weeks = self.est.estimate_phase_weeks(phase, study_hours_per_week=10.0)
        assert weeks == pytest.approx(2.0)

    def test_estimate_roadmap_within_deadline(self) -> None:
        roadmap = Roadmap(
            id=new_id(), profile_id="p1", title="Test",
            phases=[
                RoadmapPhase(
                    id=new_id(), roadmap_id="r1", phase_number=1, name="P1",
                    skills=[make_skill(SkillLevel.MISSING, SkillLevel.FAMILIAR, hours=40.0)],
                )
            ]
        )
        result = self.est.estimate_roadmap(roadmap, study_hours_per_week=10.0, deadline_weeks=8.0)
        assert result.estimated_hours == pytest.approx(40.0)
        assert result.weeks_at_rate == pytest.approx(4.0)
        assert result.is_within_deadline is True
        assert result.slack_weeks == pytest.approx(4.0)

    def test_fill_skill_estimates_populates_zero_hours(self) -> None:
        skills = [make_skill(SkillLevel.MISSING, SkillLevel.PROFICIENT, hours=0.0)]
        filled = self.est.fill_skill_estimates(skills)
        assert filled[0].estimated_hours > 0
