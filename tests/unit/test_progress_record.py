"""Unit tests for ProgressRecord and ProgressStatus."""

from __future__ import annotations

from roadmap.domain.entities.progress_record import ProgressRecord, ProgressStatus


def test_progress_record_defaults() -> None:
    rec = ProgressRecord(
        profile_id="p1",
        skill_id="s1",
        skill_name="Python",
    )
    assert rec.status == ProgressStatus.NOT_STARTED
    assert rec.completion_percentage == 0.0
    assert rec.planned_hours == 0.0
    assert rec.actual_hours == 0.0
    assert not rec.is_complete
    assert rec.started_at is None
    assert rec.completed_at is None


def test_progress_record_update() -> None:
    rec = ProgressRecord(
        profile_id="p1",
        skill_id="s1",
        skill_name="Python",
        planned_hours=20.0,
    )

    rec.update_progress(percentage=50.0, actual_hours=10.0, notes="Halfway done")
    assert rec.completion_percentage == 50.0
    assert rec.actual_hours == 10.0
    assert rec.status == ProgressStatus.IN_PROGRESS
    assert rec.started_at is not None
    assert rec.completed_at is None
    assert not rec.is_complete

    # Reach 100%
    rec.update_progress(percentage=100.0, actual_hours=22.0)
    assert rec.completion_percentage == 100.0
    assert rec.is_complete
    assert rec.status == ProgressStatus.COMPLETED
    assert rec.completed_at is not None


def test_progress_record_clamping() -> None:
    rec = ProgressRecord(profile_id="p1", skill_id="s1")
    rec.update_progress(percentage=150.0)
    assert rec.completion_percentage == 100.0

    rec.update_progress(percentage=-20.0)
    assert rec.completion_percentage == 0.0

    # Negative actual_hours ignored
    rec.update_progress(percentage=10.0, actual_hours=-5.0)
    assert rec.actual_hours == 0.0


def test_progress_record_custom_status_transitions() -> None:
    rec = ProgressRecord(profile_id="p1", skill_id="s1")
    rec.update_progress(percentage=20.0, status=ProgressStatus.BLOCKED)
    assert rec.status == ProgressStatus.BLOCKED
    assert not rec.is_complete

    rec.update_progress(percentage=20.0, status=ProgressStatus.SKIPPED)
    assert rec.status == ProgressStatus.SKIPPED
