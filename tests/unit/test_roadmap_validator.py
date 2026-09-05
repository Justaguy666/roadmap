"""Unit tests for RoadmapValidator domain service."""

from __future__ import annotations

from roadmap.domain.entities.roadmap import Milestone, Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.services.roadmap_validator import IssueType, RoadmapValidator
from roadmap.shared.ids import new_id


def make_profile(hours_per_day: float = 2.0, deadline_months: int = 12) -> UserProfile:
    return UserProfile(
        id=new_id(), name="Alice",
        target_goal="Become a Game Programmer",
        study_hours_per_day=hours_per_day,
        deadline_months=deadline_months,
    )


def make_skill(name: str = "C++", hours: float = 40.0) -> Skill:
    return Skill(
        id=new_id(), profile_id="p1", name=name,
        estimated_hours=hours,
    )


def make_phase(phase_number: int = 1, skills: list[Skill] | None = None) -> RoadmapPhase:
    return RoadmapPhase(
        id=new_id(), roadmap_id="r1",
        phase_number=phase_number,
        name=f"Phase {phase_number}",
        objective="Learn stuff",
        skills=skills or [make_skill()],
        estimated_weeks=4.0,
    )


def make_roadmap(phases: list[RoadmapPhase], total_hours: float = 200.0) -> Roadmap:
    return Roadmap(
        id=new_id(), profile_id="p1",
        title="Test Roadmap",
        phases=phases,
        total_estimated_hours=total_hours,
        total_weeks=20,
    )


class TestRoadmapValidator:
    def setup_method(self) -> None:
        self.validator = RoadmapValidator()

    def test_valid_roadmap_passes(self) -> None:
        roadmap = make_roadmap([make_phase()])
        profile = make_profile()
        result = self.validator.validate(roadmap, profile)
        assert result.is_valid

    def test_empty_phase_is_error(self) -> None:
        empty_phase = RoadmapPhase(
            id=new_id(), roadmap_id="r1", phase_number=1, name="Empty",
            objective="nothing", skills=[], estimated_weeks=2.0,
        )
        roadmap = make_roadmap([empty_phase])
        profile = make_profile()
        result = self.validator.validate(roadmap, profile)
        errors = [i for i in result.errors if i.issue_type == IssueType.EMPTY_PHASE]
        assert errors

    def test_duplicate_skill_within_phase_is_warning(self) -> None:
        skill1 = make_skill("C++")
        skill2 = make_skill("C++")
        phase = make_phase(skills=[skill1, skill2])
        roadmap = make_roadmap([phase])
        result = self.validator.validate(roadmap, make_profile())
        warnings = [i for i in result.warnings if i.issue_type == IssueType.DUPLICATE_SKILL]
        assert warnings

    def test_unrealistic_workload_is_error(self) -> None:
        # 1 hour/day for 1 month = ~26 hours total; roadmap needs 500h
        profile = make_profile(hours_per_day=1.0, deadline_months=1)
        roadmap = make_roadmap([make_phase()], total_hours=500.0)
        result = self.validator.validate(roadmap, profile)
        errors = [i for i in result.errors if i.issue_type == IssueType.UNREALISTIC_WORKLOAD]
        assert errors

    def test_missing_objective_is_warning(self) -> None:
        phase = RoadmapPhase(
            id=new_id(), roadmap_id="r1", phase_number=1, name="P1",
            objective="",  # missing
            skills=[make_skill()],
            estimated_weeks=4.0,
        )
        roadmap = make_roadmap([phase])
        result = self.validator.validate(roadmap, make_profile())
        warnings = [i for i in result.warnings if i.issue_type == IssueType.MISSING_OBJECTIVE]
        assert warnings

    def test_milestone_without_criteria_is_warning(self) -> None:
        milestone = Milestone(
            id=new_id(), phase_id="p1", name="M1",
            exit_criteria=[],  # empty
        )
        phase = make_phase()
        phase.milestones = [milestone]
        roadmap = make_roadmap([phase])
        result = self.validator.validate(roadmap, make_profile())
        warnings = [
            i for i in result.warnings
            if i.issue_type == IssueType.MISSING_MILESTONE_CRITERIA
        ]
        assert warnings
