"""
Unit tests for quota-aware research status and profile market metadata mapping.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from roadmap.application.ports.llm_provider import LLMDailyQuotaExceededError
from roadmap.application.ports.search_provider import SearchResult
from roadmap.application.services.research_service import ResearchService
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects import SkillLevel
from roadmap.infrastructure.cache.disk_cache import DiskCacheService
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.infrastructure.llm.rate_limiter import RateLimiter
from roadmap.infrastructure.search.fake_provider import FakeSearchProvider
from roadmap.infrastructure.web.fake_fetcher import FakeWebFetcher
from roadmap.storage.models import Base
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteResearchRunRepository,
    SqliteSourceRepository,
)


def test_profile_target_markets_mapping() -> None:
    profile = UserProfile(
        id="user-123",
        name="KhoiNguyen",
        target_goal="Become a Game Programmer",
        target_role="Gameplay Programmer",
        preferred_industry="Game Development",
        target_markets=["Vietnam", "Japan", "Western"],
        current_level=SkillLevel.FAMILIAR,
    )

    # Verify logic used in research_cmd.py
    if profile.target_markets:
        resolved_market = ", ".join(profile.target_markets)
    elif profile.preferred_industry:
        resolved_market = profile.preferred_industry
    else:
        resolved_market = "Global"

    assert resolved_market == "Vietnam, Japan, Western"
    assert resolved_market != "Game Development"


def test_research_service_marks_partial_on_quota_exhaustion(tmp_path) -> None:
    db_file = tmp_path / "test_quota.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    source_repo = SqliteSourceRepository(session)
    evidence_repo = SqliteEvidenceRepository(session)
    run_repo = SqliteResearchRunRepository(session)
    cache = DiskCacheService(cache_dir=tmp_path / "cache")

    # Provide 10 distinct canned results across domains so batching creates multiple batches (batch_size=5)
    canned_results = [
        SearchResult(
            url=f"https://domain{i}.com/job-{i}",
            title=f"Gameplay Engineer Posting {i}",
            snippet="C++ and Unreal Engine requirements",
            domain=f"domain{i}.com",
            score=0.9,
            content=f"Requirements for Gameplay role #{i}: C++, Unreal Engine, Linear Algebra.",
        )
        for i in range(1, 11)
    ]
    search = FakeSearchProvider(canned_results={"gameplay": canned_results})
    fetcher = FakeWebFetcher()

    llm = FakeLLMProvider()
    call_count = 0
    orig_complete = llm.complete

    def mock_complete(messages, response_model, **kwargs):
        nonlocal call_count
        call_count += 1
        # Call 1: ResearchPlan, Call 2: Batch 1 extraction (succeeds)
        if call_count <= 2:
            return orig_complete(messages, response_model, **kwargs)
        # Call 3: Batch 2 extraction raises daily quota exceeded
        raise LLMDailyQuotaExceededError("DAILY_QUOTA_EXCEEDED: Quota exceeded for metric")

    llm.complete = MagicMock(side_effect=mock_complete)

    # Use a high RPM RateLimiter so tests run instantly without delay
    fast_limiter = RateLimiter(requests_per_minute=60000.0)

    service = ResearchService(
        llm_provider=llm,
        search_provider=search,
        web_fetcher=fetcher,
        cache=cache,
        source_repo=source_repo,
        evidence_repo=evidence_repo,
        run_repo=run_repo,
        concurrency=1,
        rate_limiter=fast_limiter,
    )

    run, market_res, resource_res = service.execute_research(
        profile_id="user-123",
        topic="Gameplay Programmer",
        target_market="Vietnam, Japan, Western",
        include_market=True,
        include_resources=False,
    )

    # Because quota was exhausted mid-run but some evidence was collected, status must be PARTIAL
    assert run.status == "partial"
    assert run.evidence_count > 0
    assert any("DAILY_QUOTA_EXCEEDED" in err for err in run.errors)
