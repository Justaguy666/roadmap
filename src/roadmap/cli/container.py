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

from roadmap.application.ports.llm_provider import LLMProvider
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

    if selected == "openai":
        return OpenAIProvider(
            api_key=api_key or settings.openai_api_key,
            model=model or settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            max_retries=settings.llm_max_retries,
        )

    raise ValueError(f"Unsupported LLM provider: {selected!r}. Valid options: 'openai', 'fake'")


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
    provider = llm_provider or get_llm_provider()
    with get_session() as session:
        profile_repo = SqliteProfileRepository(session)
        roadmap_repo = SqliteRoadmapRepository(session)
        skill_repo = SqliteSkillRepository(session)

        analyze_uc = AnalyzeGoalUseCase(llm_provider=provider)
        generate_uc = GenerateRoadmapUseCase(
            llm_provider=provider,
            profile_repo=profile_repo,
            roadmap_repo=roadmap_repo,
            skill_repo=skill_repo,
            max_retries=settings.llm_max_retries,
        )

        yield (profile_repo, roadmap_repo, generate_uc, analyze_uc)
