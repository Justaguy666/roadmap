"""Unit tests for DeviationDetector."""

from __future__ import annotations

from roadmap.domain.entities.adaptation import DeviationStatus
from roadmap.domain.entities.feedback import LearningFeedback
from roadmap.domain.entities.progress_record import ProgressRecord, ProgressStatus
from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.services.deviation_detector import DeviationDetector
from roadmap.domain.value_objects.enums import Priority, SkillLevel


def _create_test_roadmap() -> Roadmap:
    s1 = Skill(
        id="s1",
        profile_id="p1",
        name="C++",
        category="prog",
        description="",
        current_level=SkillLevel.MISSING,
        target_level=SkillLevel.PROFICIENT,
        priority=Priority.CRITICAL,
        estimated_hours=40.0,
    )
    s2 = Skill(
        id="s2",
        profile_id="p1",
        name="Data Structures",
        category="algo",
        description="",
        current_level=SkillLevel.MISSING,
        target_level=SkillLevel.PROFICIENT,
        priority=Priority.HIGH,
        estimated_hours=40.0,
    )
    phase = RoadmapPhase(
        id="ph1",
        phase_number=1,
        name="Phase 1",
        skills=[s1, s2],
        estimated_weeks=4.0,
    )
    rm = Roadmap(
        id="rm1",
        profile_id="p1",
        title="Test Roadmap",
        phases=[phase],
        total_estimated_hours=80.0,
        total_weeks=4,
    )
    return rm


def test_deviation_on_track() -> None:
    detector = DeviationDetector()
    rm = _create_test_roadmap()

    # Log 20h for s1 and 50% completion (pace: 1.0x)
    records = [
        ProgressRecord(
            profile_id="p1",
            skill_id="s1",
            skill_name="C++",
            completion_percentage=50.0,
            actual_hours=20.0,
            planned_hours=40.0,
            status=ProgressStatus.IN_PROGRESS,
        )
    ]

    report = detector.analyze_deviation(rm, records)
    assert report.status == DeviationStatus.ON_TRACK
    assert report.velocity_ratio == 1.0
    assert not report.requires_adaptation


def test_deviation_critical_on_blocker_and_low_velocity() -> None:
    detector = DeviationDetector()
    rm = _create_test_roadmap()

    # Log 30h on s1 for only 10% progress and marked BLOCKED
    records = [
        ProgressRecord(
            profile_id="p1",
            skill_id="s1",
            skill_name="C++",
            completion_percentage=10.0,
            actual_hours=30.0,
            planned_hours=40.0,
            status=ProgressStatus.BLOCKED,
        ),
        ProgressRecord(
            profile_id="p1",
            skill_id="s2",
            skill_name="Data Structures",
            completion_percentage=0.0,
            actual_hours=10.0,
            planned_hours=40.0,
            status=ProgressStatus.BLOCKED,
        ),
    ]

    report = detector.analyze_deviation(rm, records)
    assert report.status == DeviationStatus.CRITICAL
    assert report.requires_adaptation
    assert "C++" in report.blocked_skills
    assert "Data Structures" in report.blocked_skills
    assert report.velocity_ratio < 0.5


def test_deviation_with_feedback_blockers() -> None:
    detector = DeviationDetector()
    rm = _create_test_roadmap()

    records = [
        ProgressRecord(
            profile_id="p1",
            skill_id="s1",
            skill_name="C++",
            completion_percentage=20.0,
            actual_hours=15.0,
            planned_hours=40.0,
        )
    ]
    feedbacks = [
        LearningFeedback(
            profile_id="p1",
            roadmap_id="rm1",
            skill_id="s1",
            skill_name="C++",
            difficulty=5,
            blocked_reason="Cannot understand pointer arithmetic",
        )
    ]

    report = detector.analyze_deviation(rm, records, feedbacks)
    assert "C++" in report.blocked_skills
    assert report.status in (DeviationStatus.WARNING, DeviationStatus.CRITICAL)


def test_deviation_planned_hours_zero_and_actual_zero() -> None:
    detector = DeviationDetector()
    rm = _create_test_roadmap()
    # Zero actual hours and zero progress
    records: list[ProgressRecord] = []
    report = detector.analyze_deviation(rm, records)
    assert report.status == DeviationStatus.ON_TRACK
    assert report.velocity_ratio == 1.0
    assert report.total_actual_hours == 0.0
    assert not report.requires_adaptation


def test_deviation_zero_planned_hours_in_roadmap() -> None:
    detector = DeviationDetector()
    s_zero = Skill(
        id="sz",
        profile_id="p1",
        name="Reading",
        category="misc",
        description="",
        estimated_hours=0.0,
    )
    phase = RoadmapPhase(
        id="ph0",
        phase_number=1,
        name="Phase 0",
        skills=[s_zero],
        estimated_weeks=1.0,
    )
    rm = Roadmap(
        id="rm0",
        profile_id="p1",
        title="Zero Hours Roadmap",
        phases=[phase],
        total_estimated_hours=0.0,
        total_weeks=1,
    )
    records = [
        ProgressRecord(
            profile_id="p1",
            skill_id="sz",
            skill_name="Reading",
            completion_percentage=100.0,
            actual_hours=5.0,
        )
    ]
    report = detector.analyze_deviation(rm, records)
    assert report.total_planned_hours == 0.0
    assert report.total_actual_hours == 5.0
    assert report.actual_completion_percentage == 100.0
    assert report.status == DeviationStatus.ON_TRACK


def test_deviation_skipped_and_blocked_statuses() -> None:
    detector = DeviationDetector()
    rm = _create_test_roadmap()
    records = [
        ProgressRecord(
            profile_id="p1",
            skill_id="s1",
            skill_name="C++",
            status=ProgressStatus.SKIPPED,
            completion_percentage=0.0,
            actual_hours=0.0,
        ),
        ProgressRecord(
            profile_id="p1",
            skill_id="s2",
            skill_name="Data Structures",
            status=ProgressStatus.BLOCKED,
            completion_percentage=10.0,
            actual_hours=15.0,
        ),
    ]
    report = detector.analyze_deviation(rm, records)
    assert "Data Structures" in report.blocked_skills
    assert report.status in (DeviationStatus.WARNING, DeviationStatus.CRITICAL)
    assert report.requires_adaptation


def test_deviation_100_percent_progress() -> None:
    detector = DeviationDetector()
    rm = _create_test_roadmap()
    records = [
        ProgressRecord(
            profile_id="p1",
            skill_id="s1",
            skill_name="C++",
            status=ProgressStatus.COMPLETED,
            completion_percentage=100.0,
            actual_hours=35.0,
        ),
        ProgressRecord(
            profile_id="p1",
            skill_id="s2",
            skill_name="Data Structures",
            status=ProgressStatus.COMPLETED,
            completion_percentage=100.0,
            actual_hours=40.0,
        ),
    ]
    report = detector.analyze_deviation(rm, records)
    assert report.actual_completion_percentage == 100.0
    assert report.status == DeviationStatus.ON_TRACK
    assert not report.requires_adaptation
