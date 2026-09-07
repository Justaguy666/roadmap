"""Integration tests for MVP-5: Progress Tracking, Feedback & Adaptive Replanning."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from roadmap.agents.adaptation_agent import AdaptationAgent
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.application.use_cases.adapt_roadmap import AdaptRoadmapUseCase
from roadmap.application.use_cases.record_feedback import RecordFeedbackUseCase
from roadmap.application.use_cases.record_progress import UpdateProgressUseCase
from roadmap.domain.entities.progress_record import ProgressStatus
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects.enums import LLMWorkflow
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.storage.models.base import Base
from roadmap.storage.repositories.adaptation_repository import SqliteAdaptationRepository
from roadmap.storage.repositories.feedback_repository import SqliteFeedbackRepository
from roadmap.storage.repositories.llm_usage_repository import SqliteLLMUsageRepository
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.progress_repository import SqliteProgressRepository
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_mvp5_full_adaptive_lifecycle(db_session) -> None:
    # 1. Setup repos
    profile_repo = SqliteProfileRepository(db_session)
    roadmap_repo = SqliteRoadmapRepository(db_session)
    progress_repo = SqliteProgressRepository(db_session)
    feedback_repo = SqliteFeedbackRepository(db_session)
    adaptation_repo = SqliteAdaptationRepository(db_session)
    usage_repo = SqliteLLMUsageRepository(db_session)

    budget_mgr = LLMBudgetManager(repository=usage_repo, daily_budget=10)
    fake_llm = FakeLLMProvider()

    # 2. Seed profile & roadmap
    profile = UserProfile(name="Test Learner", target_goal="Become Gameplay Programmer")
    profile_repo.save(profile)

    # Manually build initial domain roadmap from fake roadmap result
    from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
    from roadmap.domain.entities.skill import Skill
    from roadmap.domain.value_objects.enums import Priority, SkillLevel

    s1 = Skill(
        id="sk1",
        profile_id=profile.id,
        name="C++",
        category="programming",
        description="",
        current_level=SkillLevel.MISSING,
        target_level=SkillLevel.PROFICIENT,
        priority=Priority.CRITICAL,
        estimated_hours=40.0,
    )
    s2 = Skill(
        id="sk2",
        profile_id=profile.id,
        name="Linear Algebra",
        category="math",
        description="",
        current_level=SkillLevel.MISSING,
        target_level=SkillLevel.PROFICIENT,
        priority=Priority.HIGH,
        estimated_hours=30.0,
        prerequisite_names=["C++"],
    )

    initial_phase = RoadmapPhase(
        id="p1",
        phase_number=1,
        name="Foundations",
        skills=[s1, s2],
        estimated_weeks=6.0,
    )
    initial_roadmap = Roadmap(
        id="rm1",
        profile_id=profile.id,
        title="Gameplay Roadmap",
        version=1,
        phases=[initial_phase],
        total_estimated_hours=70.0,
        total_weeks=6,
    )
    roadmap_repo.save(initial_roadmap)

    # 3. Record Progress with low velocity & blocker
    progress_uc = UpdateProgressUseCase(
        roadmap_repo=roadmap_repo,
        progress_repo=progress_repo,
        feedback_repo=feedback_repo,
    )

    # User spent 25h but only made 15% progress on C++ and is blocked
    res = progress_uc.execute(
        profile_id=profile.id,
        skill_identifier="C++",
        percentage=15.0,
        actual_hours=25.0,
        status=ProgressStatus.BLOCKED,
        notes="Stuck on pointers and memory corruption.",
    )
    assert res.record.completion_percentage == 15.0
    assert res.record.status == ProgressStatus.BLOCKED
    assert res.deviation_report.status.value in ("WARNING", "CRITICAL")
    assert "C++" in res.deviation_report.blocked_skills

    # 4. Record qualitative feedback
    feedback_uc = RecordFeedbackUseCase(
        roadmap_repo=roadmap_repo,
        feedback_repo=feedback_repo,
    )
    fb = feedback_uc.execute(
        profile_id=profile.id,
        difficulty=5,
        confidence=1,
        satisfaction=2,
        skill_identifier="C++",
        blocked_reason="Segfaults in pointer arrays",
        free_text="Need more basic memory drills before data structures.",
    )
    assert fb.difficulty == 5
    assert fb.blocked_reason == "Segfaults in pointer arrays"

    # 5. Adapt roadmap
    agent = AdaptationAgent(llm_provider=fake_llm, budget_manager=budget_mgr)
    adapt_uc = AdaptRoadmapUseCase(
        roadmap_repo=roadmap_repo,
        progress_repo=progress_repo,
        feedback_repo=feedback_repo,
        adaptation_repo=adaptation_repo,
        adaptation_agent=agent,
    )

    candidate_res = adapt_uc.prepare_adaptation(profile.id, force=True)
    assert candidate_res.requires_adaptation
    assert candidate_res.candidate_roadmap.version == 2

    # Verify candidate roadmap contents before applying
    applied_rm = adapt_uc.apply_adaptation(candidate_res)
    assert applied_rm.version == 2
    assert applied_rm.id != initial_roadmap.id

    # 6. Verify version audit & history persistence
    latest_rm = roadmap_repo.load_latest(profile.id)
    assert latest_rm is not None
    assert latest_rm.version == 2

    v1_rm = roadmap_repo.load_by_version(profile.id, 1)
    assert v1_rm is not None
    assert v1_rm.version == 1

    adapt_rec = adaptation_repo.load_by_version(profile.id, 2)
    assert adapt_rec is not None
    assert adapt_rec.previous_version == 1
    assert adapt_rec.new_version == 2
    assert "C++" in str(adapt_rec.changes_summary)

    # 7. Verify adaptation LLM request budget was consumed
    status = budget_mgr.get_quota_status()
    assert status.workflow_budgets[LLMWorkflow.ADAPTATION].used >= 1
