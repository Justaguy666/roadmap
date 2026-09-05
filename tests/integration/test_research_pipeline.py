"""Integration tests for ResearchService pipeline."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from roadmap.application.services.research_service import ResearchService
from roadmap.infrastructure.cache.disk_cache import DiskCacheService
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.infrastructure.search.fake_provider import FakeSearchProvider
from roadmap.infrastructure.web.fake_fetcher import FakeWebFetcher
from roadmap.storage.models import Base
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteResearchRunRepository,
    SqliteSourceRepository,
)


def test_research_service_pipeline_end_to_end(tmp_path) -> None:
    db_file = tmp_path / "test_research.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    source_repo = SqliteSourceRepository(session)
    evidence_repo = SqliteEvidenceRepository(session)
    run_repo = SqliteResearchRunRepository(session)

    cache = DiskCacheService(cache_dir=tmp_path / "cache", default_ttl_seconds=3600)
    llm = FakeLLMProvider()
    search = FakeSearchProvider()
    fetcher = FakeWebFetcher()

    service = ResearchService(
        llm_provider=llm,
        search_provider=search,
        web_fetcher=fetcher,
        cache=cache,
        source_repo=source_repo,
        evidence_repo=evidence_repo,
        run_repo=run_repo,
        concurrency=2,
    )

    run, market_res, resource_res = service.execute_research(
        profile_id="test-profile-123",
        topic="Backend Engineering",
        target_market="US Tech Companies",
        focus_skills=["Python", "FastAPI"],
        include_market=True,
        include_resources=True,
    )

    assert run.status in ("completed", "partial")
    assert run.source_count > 0
    assert run.evidence_count > 0

    # Verify persistence in SQLite
    latest_run = run_repo.get_latest(profile_id="test-profile-123")
    assert latest_run is not None
    assert latest_run.id == run.id

    sources = source_repo.list_all()
    assert len(sources) > 0

    evidence_items = evidence_repo.find_by_skill("C++")
    assert len(evidence_items) > 0
    assert evidence_items[0].source_id is not None
