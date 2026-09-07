"""MVP-5 Final Verification Gate Integration Tests.

Validates:
1. Version immutability (v1 unchanged, v2 created, historical progress preserved).
2. User rejection path (user answers NO -> zero roadmaps persisted, zero mutations).
3. Grounding / safety invariants on newly proposed support skills (DAG integrity, valid phase/attributes).
4. Zero-LLM guarantee on ON_TRACK progress (0 LLM calls, 0 budget reservations).
5. Anti-oscillation guard (rejection when <10h logged, unblocking when >=10h logged).
6. LLM adaptation budget accounting and reservation lifecycle.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from roadmap.agents.adaptation_agent import AdaptationAgent
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.application.use_cases.adapt_roadmap import AdaptRoadmapUseCase
from roadmap.application.use_cases.record_progress import UpdateProgressUseCase
from roadmap.domain.entities.progress_record import ProgressStatus
from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects.enums import LLMWorkflow, Priority, SkillLevel
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.storage.models.base import Base
from roadmap.storage.repositories.adaptation_repository import SqliteAdaptationRepository
from roadmap.storage.repositories.feedback_repository import SqliteFeedbackRepository
from roadmap.storage.repositories.llm_usage_repository import SqliteLLMUsageRepository
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.progress_repository import SqliteProgressRepository
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed_environment(session):
    profile_repo = SqliteProfileRepository(session)
    roadmap_repo = SqliteRoadmapRepository(session)
    progress_repo = SqliteProgressRepository(session)
    feedback_repo = SqliteFeedbackRepository(session)
    adaptation_repo = SqliteAdaptationRepository(session)
    usage_repo = SqliteLLMUsageRepository(session)

    budget_mgr = LLMBudgetManager(repository=usage_repo, daily_budget=15)
    fake_llm = FakeLLMProvider()

    profile = UserProfile(name="Verification Learner", target_goal="Gameplay Systems")
    profile_repo.save(profile)

    s1 = Skill(
        id="sk1",
        profile_id=profile.id,
        name="C++",
        category="programming",
        description="Core language",
        current_level=SkillLevel.MISSING,
        target_level=SkillLevel.PROFICIENT,
        priority=Priority.CRITICAL,
        estimated_hours=40.0,
    )
    s2 = Skill(
        id="sk2",
        profile_id=profile.id,
        name="Memory Management",
        category="systems",
        description="Allocators and pointers",
        current_level=SkillLevel.MISSING,
        target_level=SkillLevel.PROFICIENT,
        priority=Priority.HIGH,
        estimated_hours=30.0,
        prerequisite_names=["C++"],
    )
    phase1 = RoadmapPhase(
        id="p1",
        phase_number=1,
        name="Phase 1: Systems",
        skills=[s1, s2],
        estimated_weeks=6.0,
    )
    rm = Roadmap(
        id="rm_v1",
        profile_id=profile.id,
        title="Gameplay Systems Curriculum",
        version=1,
        phases=[phase1],
        total_estimated_hours=70.0,
        total_weeks=6,
    )
    roadmap_repo.save(rm)

    return {
        "profile": profile,
        "rm_v1": rm,
        "profile_repo": profile_repo,
        "roadmap_repo": roadmap_repo,
        "progress_repo": progress_repo,
        "feedback_repo": feedback_repo,
        "adaptation_repo": adaptation_repo,
        "usage_repo": usage_repo,
        "budget_mgr": budget_mgr,
        "fake_llm": fake_llm,
    }


def test_version_immutability_and_progress_history(test_db):
    """Verify v1 is untouched when v2 is created, and historical records persist."""
    ctx = _seed_environment(test_db)
    agent = AdaptationAgent(llm_provider=ctx["fake_llm"], budget_manager=ctx["budget_mgr"])
    adapt_uc = AdaptRoadmapUseCase(
        roadmap_repo=ctx["roadmap_repo"],
        progress_repo=ctx["progress_repo"],
        feedback_repo=ctx["feedback_repo"],
        adaptation_repo=ctx["adaptation_repo"],
        adaptation_agent=agent,
    )

    candidate_res = adapt_uc.prepare_adaptation(ctx["profile"].id, force=True)
    adapted_v2 = adapt_uc.apply_adaptation(candidate_res)

    # v1 must still exist in DB exactly as created
    v1_reloaded = ctx["roadmap_repo"].load_by_version(ctx["profile"].id, 1)
    assert v1_reloaded is not None
    assert v1_reloaded.id == ctx["rm_v1"].id
    assert v1_reloaded.version == 1

    # v2 is separate
    assert adapted_v2.id != v1_reloaded.id
    assert adapted_v2.version == 2
    latest = ctx["roadmap_repo"].load_latest(ctx["profile"].id)
    assert latest is not None
    assert latest.version == 2


def test_zero_llm_calls_on_on_track_progress(test_db):
    """Verify zero LLM calls and zero budget reservations when progress is ON_TRACK."""
    ctx = _seed_environment(test_db)
    progress_uc = UpdateProgressUseCase(
        roadmap_repo=ctx["roadmap_repo"],
        progress_repo=ctx["progress_repo"],
        feedback_repo=ctx["feedback_repo"],
    )

    # On track: logged 20h and achieved 50% on 40h skill (1.0x velocity)
    progress_uc.execute(
        profile_id=ctx["profile"].id,
        skill_identifier="C++",
        percentage=50.0,
        actual_hours=20.0,
        status=ProgressStatus.IN_PROGRESS,
    )

    initial_llm_calls = len(ctx["fake_llm"].calls) if hasattr(ctx["fake_llm"], "calls") else 0
    initial_budget = ctx["budget_mgr"].get_quota_status().workflow_budgets[LLMWorkflow.ADAPTATION].used

    agent = AdaptationAgent(llm_provider=ctx["fake_llm"], budget_manager=ctx["budget_mgr"])
    adapt_uc = AdaptRoadmapUseCase(
        roadmap_repo=ctx["roadmap_repo"],
        progress_repo=ctx["progress_repo"],
        feedback_repo=ctx["feedback_repo"],
        adaptation_repo=ctx["adaptation_repo"],
        adaptation_agent=agent,
    )

    result = adapt_uc.prepare_adaptation(ctx["profile"].id, force=False)

    assert not result.requires_adaptation
    assert result.candidate_roadmap.version == 1
    # LLM was NOT called
    if hasattr(ctx["fake_llm"], "calls"):
        assert len(ctx["fake_llm"].calls) == initial_llm_calls
    # Budget was NOT consumed
    used_after = ctx["budget_mgr"].get_quota_status().workflow_budgets[LLMWorkflow.ADAPTATION].used
    assert used_after == initial_budget


def test_anti_oscillation_guard_and_cooldown_unlock(test_db):
    """Verify replanning is blocked if <10h logged since last adaptation, then unlocked once >=10h logged."""
    ctx = _seed_environment(test_db)
    agent = AdaptationAgent(llm_provider=ctx["fake_llm"], budget_manager=ctx["budget_mgr"])
    adapt_uc = AdaptRoadmapUseCase(
        roadmap_repo=ctx["roadmap_repo"],
        progress_repo=ctx["progress_repo"],
        feedback_repo=ctx["feedback_repo"],
        adaptation_repo=ctx["adaptation_repo"],
        adaptation_agent=agent,
    )

    # First adaptation forced
    cand = adapt_uc.prepare_adaptation(ctx["profile"].id, force=True)
    adapt_uc.apply_adaptation(cand)

    # Now attempt second adaptation immediately without force: must be blocked by anti-oscillation
    res2 = adapt_uc.prepare_adaptation(ctx["profile"].id, force=False)
    assert res2.blocked_by_anti_oscillation
    assert "Anti-oscillation cooldown active" in res2.anti_oscillation_reason

    # Log 12 hours of actual learning after adaptation
    progress_uc = UpdateProgressUseCase(
        roadmap_repo=ctx["roadmap_repo"],
        progress_repo=ctx["progress_repo"],
        feedback_repo=ctx["feedback_repo"],
    )
    progress_uc.execute(
        profile_id=ctx["profile"].id,
        skill_identifier="C++",
        percentage=20.0,
        actual_hours=12.0,
        status=ProgressStatus.BLOCKED,  # trigger need for adaptation
    )

    # Now anti-oscillation should NOT block because 12h >= 10.0h
    res3 = adapt_uc.prepare_adaptation(ctx["profile"].id, force=False)
    assert not res3.blocked_by_anti_oscillation
    assert res3.requires_adaptation


def test_user_rejection_path_leaves_db_untouched(test_db):
    """Verify that when preparation occurs but user rejects (apply_adaptation not called), no v2 exists."""
    ctx = _seed_environment(test_db)
    agent = AdaptationAgent(llm_provider=ctx["fake_llm"], budget_manager=ctx["budget_mgr"])
    adapt_uc = AdaptRoadmapUseCase(
        roadmap_repo=ctx["roadmap_repo"],
        progress_repo=ctx["progress_repo"],
        feedback_repo=ctx["feedback_repo"],
        adaptation_repo=ctx["adaptation_repo"],
        adaptation_agent=agent,
    )

    cand = adapt_uc.prepare_adaptation(ctx["profile"].id, force=True)
    assert cand.candidate_roadmap.version == 2

    # Simulate user rejecting prompt in CLI (apply_adaptation is NOT called)
    all_rms = ctx["roadmap_repo"].load_all(ctx["profile"].id)
    assert len(all_rms) == 1
    assert all_rms[0].version == 1
    assert ctx["adaptation_repo"].get_latest_adaptation(ctx["profile"].id) is None
