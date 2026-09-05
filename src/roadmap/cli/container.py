"""
Dependency injection container for the CLI.

The container creates and wires all dependencies:
  database session → repositories → use cases
  LLM provider selection → agents & use cases

This keeps CLI commands free from knowing about SQLAlchemy, OpenAI SDK,
or any other infrastructure detail.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from roadmap.application.ports.infrastructure import Cache, WebFetcher
from roadmap.application.ports.llm_provider import LLMProvider
from roadmap.application.ports.search_provider import SearchProvider
from roadmap.application.services.research_service import ResearchService
from roadmap.application.use_cases.analyze_goal import AnalyzeGoalUseCase
from roadmap.application.use_cases.generate_roadmap import GenerateRoadmapUseCase
from roadmap.application.use_cases.profile_use_cases import (
    CreateProfileUseCase,
    DeleteProfileUseCase,
    GetProfileUseCase,
    UpdateProfileUseCase,
)
from roadmap.config.settings import settings
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.infrastructure.llm.openai_provider import OpenAIProvider
from roadmap.storage.database import create_all_tables, get_session
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.progress_repository import SqliteProgressRepository
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteResearchRunRepository,
    SqliteSourceRepository,
)
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository
from roadmap.storage.repositories.skill_repository import SqliteSkillRepository


def initialize_database() -> None:
    """Ensure the data directory and all DB tables exist."""
    settings.ensure_data_dir()
    create_all_tables()


def get_llm_provider(
    provider_name: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> LLMProvider:
    """
    Factory function for obtaining an LLMProvider instance.
    Defaults to OpenAIProvider unless configured as 'fake' or 'mock'.
    """
    selected = (provider_name or settings.llm_provider).lower().strip()

    if selected in ("fake", "mock", "test"):
        return FakeLLMProvider()

    if selected in ("gemini", "google"):
        from roadmap.infrastructure.llm.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=api_key or settings.gemini_api_key,
            model=model or settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            max_retries=settings.llm_max_retries,
        )

    if selected == "openai":
        return OpenAIProvider(
            api_key=api_key or settings.openai_api_key,
            model=model or settings.llm_model or "gpt-4o",
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            max_retries=settings.llm_max_retries,
        )

    raise ValueError(f"Unsupported LLM provider: {selected}. Valid options: 'gemini', 'openai', 'mock'")

def get_search_provider(
    provider_name: str | None = None,
    api_key: str | None = None,
) -> SearchProvider:
    """Factory for SearchProvider."""
    from roadmap.infrastructure.search.exa_provider import ExaSearchProvider
    from roadmap.infrastructure.search.fake_provider import FakeSearchProvider

    selected = (provider_name or settings.search_provider).lower().strip()
    if selected in ("mock", "fake", "test"):
        return FakeSearchProvider()
    if selected == "exa":
        key = api_key or settings.exa_api_key
        if not key:
            raise ValueError(
                "EXA_API_KEY is required to use Exa search. "
                "Set EXA_API_KEY in your .env file or environment, or set ROADMAP_SEARCH_PROVIDER=mock for offline use."
            )
        return ExaSearchProvider(api_key=key, timeout_seconds=float(settings.research_timeout_seconds))
    raise ValueError(f"Unsupported search provider: {selected!r}. Valid options: 'exa', 'mock', 'fake'")


def get_web_fetcher() -> WebFetcher:
    """Factory for WebFetcher."""
    from roadmap.infrastructure.web.fake_fetcher import FakeWebFetcher
    from roadmap.infrastructure.web.fetcher import HttpWebFetcher

    if settings.search_provider in ("mock", "fake", "test"):
        return FakeWebFetcher()
    return HttpWebFetcher()


def get_cache() -> Cache:
    """Factory for Cache."""
    from roadmap.infrastructure.cache.disk_cache import DiskCacheService

    return DiskCacheService(cache_dir=settings.cache_dir, default_ttl_seconds=settings.cache_ttl_hours * 3600)


@contextmanager
def get_profile_use_cases() -> Generator[
    tuple[CreateProfileUseCase, GetProfileUseCase, UpdateProfileUseCase, DeleteProfileUseCase], None, None
]:
    """Yield profile use cases bound to a database session."""
    with get_session() as session:
        repo = SqliteProfileRepository(session)
        yield (
            CreateProfileUseCase(repo),
            GetProfileUseCase(repo),
            UpdateProfileUseCase(repo),
            DeleteProfileUseCase(repo),
        )


@contextmanager
def get_roadmap_context() -> Generator[
    tuple[
        SqliteProfileRepository,
        SqliteSkillRepository,
        SqliteRoadmapRepository,
        SqliteProgressRepository,
    ],
    None,
    None,
]:
    """Yield all repositories for roadmap operations."""
    with get_session() as session:
        yield (
            SqliteProfileRepository(session),
            SqliteSkillRepository(session),
            SqliteRoadmapRepository(session),
            SqliteProgressRepository(session),
        )


@contextmanager
def get_generator_context(
    llm_provider: LLMProvider | None = None,
) -> Generator[
    tuple[
        SqliteProfileRepository,
        SqliteRoadmapRepository,
        GenerateRoadmapUseCase,
        AnalyzeGoalUseCase,
    ],
    None,
    None,
]:
    """Yield use cases and repositories required for goal analysis & roadmap generation."""
    from roadmap.storage.repositories.research_repository import (
        SqliteEvidenceRepository,
        SqliteRecommendationRepository,
        SqliteSourceRepository,
    )

    provider = llm_provider or get_llm_provider()
    with get_session() as session:
        profile_repo = SqliteProfileRepository(session)
        roadmap_repo = SqliteRoadmapRepository(session)
        skill_repo = SqliteSkillRepository(session)
        evidence_repo = SqliteEvidenceRepository(session)
        source_repo = SqliteSourceRepository(session)
        recommendation_repo = SqliteRecommendationRepository(session)

        analyze_uc = AnalyzeGoalUseCase(llm_provider=provider)
        generate_uc = GenerateRoadmapUseCase(
            llm_provider=provider,
            profile_repo=profile_repo,
            roadmap_repo=roadmap_repo,
            skill_repo=skill_repo,
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            recommendation_repo=recommendation_repo,
            max_retries=settings.llm_max_retries,
        )

        yield (profile_repo, roadmap_repo, generate_uc, analyze_uc)


@contextmanager
def get_research_context(
    llm_provider: LLMProvider | None = None,
) -> Generator[
    tuple[
        SqliteProfileRepository,
        SqliteSourceRepository,
        SqliteEvidenceRepository,
        SqliteResearchRunRepository,
        ResearchService | None,
    ],
    None,
    None,
]:
    """Yield repositories and ResearchService bound to a database session."""
    from roadmap.application.services.research_service import ResearchService
    from roadmap.storage.repositories.research_repository import (
        SqliteEvidenceRepository,
        SqliteResearchRunRepository,
        SqliteSourceRepository,
    )

    try:
        provider = llm_provider or get_llm_provider()
    except Exception:
        provider = None  # type: ignore[assignment]

    try:
        search = get_search_provider()
    except Exception:
        search = None  # type: ignore[assignment]

    fetcher = get_web_fetcher()
    cache = get_cache()

    with get_session() as session:
        profile_repo = SqliteProfileRepository(session)
        source_repo = SqliteSourceRepository(session)
        evidence_repo = SqliteEvidenceRepository(session)
        run_repo = SqliteResearchRunRepository(session)

        svc = None
        if provider and search:
            svc = ResearchService(
                llm_provider=provider,
                search_provider=search,
                web_fetcher=fetcher,
                cache=cache,
                source_repo=source_repo,
                evidence_repo=evidence_repo,
                run_repo=run_repo,
                concurrency=settings.research_concurrency,
            )

        yield (profile_repo, source_repo, evidence_repo, run_repo, svc)
