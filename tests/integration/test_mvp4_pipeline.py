"""Integration test for MVP-4 pipeline: Research, Graph, Evaluator Loop, and Decisions."""

from __future__ import annotations

from roadmap.application.use_cases.generate_roadmap import GenerateRoadmapUseCase
from roadmap.domain.entities.source import Evidence, Source
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects import SourceType
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteRecommendationRepository,
    SqliteSourceRepository,
)
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository
from roadmap.storage.repositories.skill_repository import SqliteSkillRepository


def test_full_mvp4_pipeline_integration(db_session) -> None:
    profile_repo = SqliteProfileRepository(db_session)
    roadmap_repo = SqliteRoadmapRepository(db_session)
    skill_repo = SqliteSkillRepository(db_session)
    evidence_repo = SqliteEvidenceRepository(db_session)
    source_repo = SqliteSourceRepository(db_session)
    rec_repo = SqliteRecommendationRepository(db_session)

    profile = UserProfile(
        name="Hero",
        target_goal="Become a Gameplay Programmer",
        target_role="Gameplay Programmer",
        study_hours_per_day=4.0,
        deadline_months=6,
    )
    profile_repo.save(profile)

    # Seed evidence & source into database
    src = Source(
        id="src-1",
        url="https://epicgames.com/careers/gameplay",
        title="Gameplay Engineer Job",
        source_type=SourceType.JOB_POSTING,
        domain="epicgames.com",
        reliability_score=0.90,
    )
    source_repo.save(src)

    ev = Evidence(
        id="ev-1",
        source_id="src-1",
        extracted_claim="Requires modern C++ and vector linear algebra.",
        relevance=0.95,
        confidence=0.90,
        associated_skill_names=["C++", "Linear Algebra"],
    )
    evidence_repo.save(ev)

    fake_llm = FakeLLMProvider()

    use_case = GenerateRoadmapUseCase(
        llm_provider=fake_llm,
        profile_repo=profile_repo,
        roadmap_repo=roadmap_repo,
        skill_repo=skill_repo,
        evidence_repo=evidence_repo,
        source_repo=source_repo,
        recommendation_repo=rec_repo,
        max_retries=3,
    )

    roadmap, goal_analysis, skill_gaps, val_result = use_case.execute(profile)

    # Assertions
    assert val_result.is_valid is True
    assert roadmap.version == 1
    assert roadmap.quality_score > 0.0
    assert len(roadmap.phases) >= 2
    assert len(roadmap.all_skills) >= 2

    # Verify persisted roadmap
    loaded_rm = roadmap_repo.load_latest(profile.id)
    assert loaded_rm is not None
    assert loaded_rm.version == 1
    assert loaded_rm.quality_score == roadmap.quality_score

    # Verify persisted recommendations
    recs = rec_repo.list_by_roadmap(roadmap.id)
    assert len(recs) > 0
    first_rec = recs[0]
    assert first_rec.decision in ("include", "postpone")
    assert "market_relevance" in first_rec.decision_factors
    assert "goal_relevance" in first_rec.decision_factors
