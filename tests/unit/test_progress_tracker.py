"""Unit tests for ProgressTracker domain service."""

from __future__ import annotations

from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill, SkillDependency
from roadmap.domain.services.progress_tracker import ProgressTracker
from roadmap.domain.value_objects import DependencyType, SkillLevel, SkillStatus
from roadmap.shared.ids import new_id


def make_skill(name: str = "Skill", status: SkillStatus = SkillStatus.PENDING) -> Skill:
    return Skill(
        id=new_id(), profile_id="p1", name=name, status=status,
    )


class TestProgressTracker:
    def setup_method(self) -> None:
        self.tracker = ProgressTracker()

    def test_mark_skill_complete_sets_status(self) -> None:
        skill = make_skill()
        update = self.tracker.mark_skill_complete("profile1", skill, "Well done")
        assert update.newly_completed is True
        assert update.new_percentage == 100.0
        assert skill.status == SkillStatus.COMPLETED
        assert update.progress_record is not None
        assert update.progress_record.is_complete

    def test_update_partial_progress(self) -> None:
        skill = make_skill()
        record = self.tracker.update_skill_progress("p1", skill, 60.0, "halfway")
        assert record.completion_percentage == 60.0
        assert not record.is_complete
        assert record.completed_at is None

    def test_update_100_sets_completed_at(self) -> None:
        skill = make_skill()
        record = self.tracker.update_skill_progress("p1", skill, 100.0)
        assert record.is_complete
        assert record.completed_at is not None

    def test_determine_unlocked_no_prerequisites(self) -> None:
        skills = [make_skill("A"), make_skill("B")]
        unlocked = self.tracker.determine_unlocked_skills(skills, [], {})
        assert "A" in unlocked
        assert "B" in unlocked

    def test_determine_unlocked_prerequisite_not_met(self) -> None:
        cpp = make_skill("C++")
        oop = make_skill("OOP")
        dep = SkillDependency(
            id=new_id(), from_skill_id=cpp.id, to_skill_id=oop.id,
            dependency_type=DependencyType.REQUIRES,
        )
        # C++ not completed yet
        unlocked = self.tracker.determine_unlocked_skills(
            [cpp, oop], [dep], {cpp.id: 50.0}
        )
        assert "OOP" not in unlocked
        assert "C++" in unlocked

    def test_determine_unlocked_prerequisite_met(self) -> None:
        cpp = make_skill("C++")
        oop = make_skill("OOP")
        dep = SkillDependency(
            id=new_id(), from_skill_id=cpp.id, to_skill_id=oop.id,
            dependency_type=DependencyType.REQUIRES,
        )
        # C++ is 85% — above threshold
        unlocked = self.tracker.determine_unlocked_skills(
            [cpp, oop], [dep], {cpp.id: 85.0}
        )
        assert "OOP" in unlocked

    def test_compute_roadmap_progress(self) -> None:
        skill_a = make_skill("A")
        skill_b = make_skill("B")
        phase = RoadmapPhase(
            id=new_id(), roadmap_id="r1", phase_number=1, name="P1",
            skills=[skill_a, skill_b], estimated_weeks=4.0,
        )
        roadmap = Roadmap(
            id=new_id(), profile_id="p1", title="R", phases=[phase]
        )
        # A is 100%, B is 0%
        progress_map = {skill_a.id: 100.0, skill_b.id: 0.0}
        computed = self.tracker.compute_roadmap_progress(roadmap, progress_map)
        assert computed["phase_1"] == 50.0
        assert computed["overall"] == 50.0

    def test_level_from_progress_boundary(self) -> None:
        skill = make_skill()
        assert self.tracker.get_current_level_from_progress(skill, 0.0) == SkillLevel.MISSING
        assert self.tracker.get_current_level_from_progress(skill, 25.0) == SkillLevel.FAMILIAR
        assert self.tracker.get_current_level_from_progress(skill, 55.0) == SkillLevel.LEARNING
        assert self.tracker.get_current_level_from_progress(skill, 80.0) == SkillLevel.PROFICIENT
        assert self.tracker.get_current_level_from_progress(skill, 95.0) == SkillLevel.MASTERED
