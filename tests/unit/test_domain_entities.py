"""Unit tests for domain entities and value objects."""

from __future__ import annotations

from roadmap.domain.entities.roadmap import Milestone, Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects import (
    Priority,
    SkillLevel,
    SkillStatus,
)
from roadmap.shared.ids import is_valid_id, new_id


class TestSkillLevel:
    def test_ordering(self) -> None:
        assert SkillLevel.MISSING < SkillLevel.FAMILIAR
        assert SkillLevel.FAMILIAR < SkillLevel.LEARNING
        assert SkillLevel.LEARNING < SkillLevel.PROFICIENT
        assert SkillLevel.PROFICIENT < SkillLevel.MASTERED

    def test_numeric_values(self) -> None:
        assert SkillLevel.MISSING.numeric() == 0
        assert SkillLevel.MASTERED.numeric() == 4

    def test_gap_from_mastered(self) -> None:
        assert SkillLevel.MISSING.gap_from_mastered == 4
        assert SkillLevel.MASTERED.gap_from_mastered == 0

    def test_ge_comparison(self) -> None:
        assert SkillLevel.PROFICIENT >= SkillLevel.FAMILIAR
        assert SkillLevel.MASTERED >= SkillLevel.MASTERED


class TestPriority:
    def test_ordering(self) -> None:
        assert Priority.LOW < Priority.MEDIUM
        assert Priority.MEDIUM < Priority.HIGH
        assert Priority.HIGH < Priority.CRITICAL

    def test_numeric(self) -> None:
        assert Priority.CRITICAL.numeric() == 4
        assert Priority.LOW.numeric() == 1


class TestSkillEntity:
    def make(self) -> Skill:
        return Skill(
            id=new_id(), profile_id="p1", name="C++",
            current_level=SkillLevel.FAMILIAR,
            target_level=SkillLevel.PROFICIENT,
        )

    def test_level_gap_calculation(self) -> None:
        skill = self.make()
        # FAMILIAR(1) → PROFICIENT(3) = gap of 2
        assert skill.level_gap == 2

    def test_no_gap_when_already_at_target(self) -> None:
        skill = Skill(
            id=new_id(), profile_id="p1", name="Git",
            current_level=SkillLevel.MASTERED,
            target_level=SkillLevel.PROFICIENT,
        )
        assert skill.level_gap == 0

    def test_is_completed(self) -> None:
        skill = self.make()
        assert not skill.is_completed
        skill.status = SkillStatus.COMPLETED
        assert skill.is_completed

    def test_composite_priority_score_range(self) -> None:
        skill = Skill(
            id=new_id(), profile_id="p1", name="Test",
            market_demand_score=0.8,
            goal_relevance_score=0.9,
        )
        score = skill.composite_priority_score
        assert 0.0 <= score <= 1.0


class TestUserProfile:
    def test_study_hours_per_week(self) -> None:
        profile = UserProfile(
            id=new_id(), name="Alice",
            target_goal="Become a developer",
            study_hours_per_day=3.0,
        )
        assert profile.study_hours_per_week == 15.0

    def test_total_available_hours(self) -> None:
        profile = UserProfile(
            id=new_id(), name="Bob",
            target_goal="Learn ML",
            study_hours_per_day=2.0,
            deadline_months=6,
        )
        # 6 months * 4.33 weeks/month * 2h/day * 5 days/week
        expected = 6 * 4.33 * 2.0 * 5
        assert abs(profile.total_available_hours - expected) < 1.0

    def test_strip_empty_skills(self) -> None:
        profile = UserProfile(
            id=new_id(), name="Carol",
            target_goal="Learn Python",
            current_skills=["", "Python", " ", "C++"],
        )
        assert "" not in profile.current_skills
        assert " " not in profile.current_skills
        assert "Python" in profile.current_skills


class TestRoadmapEntity:
    def make_roadmap(self, n_phases: int = 2) -> Roadmap:
        phases = []
        for i in range(1, n_phases + 1):
            skill = Skill(
                id=new_id(), profile_id="p1", name=f"Skill{i}",
                estimated_hours=40.0,
            )
            phases.append(RoadmapPhase(
                id=new_id(), roadmap_id="r1",
                phase_number=i, name=f"Phase {i}",
                objective="Learn stuff",
                skills=[skill],
                estimated_weeks=4.0,
            ))
        return Roadmap(id=new_id(), profile_id="p1", title="Test", phases=phases)

    def test_overall_completion_zero(self) -> None:
        roadmap = self.make_roadmap()
        assert roadmap.overall_completion_percentage == 0.0

    def test_current_phase_is_first_incomplete(self) -> None:
        roadmap = self.make_roadmap(2)
        roadmap.phases[0].is_completed = True
        assert roadmap.current_phase == roadmap.phases[1]

    def test_current_phase_none_when_all_done(self) -> None:
        roadmap = self.make_roadmap(1)
        roadmap.phases[0].is_completed = True
        assert roadmap.current_phase is None

    def test_recalculate_totals(self) -> None:
        roadmap = self.make_roadmap(2)
        # Each phase has 1 skill with 40h estimated
        roadmap.phases[0].skills[0].estimated_hours = 40.0
        roadmap.phases[1].skills[0].estimated_hours = 60.0
        roadmap.recalculate_totals()
        assert roadmap.total_estimated_hours == 100.0


class TestMilestone:
    def test_mark_achieved(self) -> None:
        m = Milestone(id=new_id(), phase_id="p1", name="M1", exit_criteria=["Do X"])
        assert not m.is_achieved
        m.mark_achieved()
        assert m.is_achieved
        assert m.achieved_at is not None


class TestIds:
    def test_new_id_is_valid(self) -> None:
        assert is_valid_id(new_id())

    def test_is_valid_id_rejects_garbage(self) -> None:
        assert not is_valid_id("not-a-uuid")
        assert not is_valid_id("")
