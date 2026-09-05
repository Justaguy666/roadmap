"""
Dependency injection container for the CLI.

The container creates and wires all dependencies:
  database session → repositories → use cases

This keeps CLI commands free from knowing about SQLAlchemy or
any other infrastructure detail.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from roadmap.application.use_cases.profile_use_cases import (
    CreateProfileUseCase,
    GetProfileUseCase,
    UpdateProfileUseCase,
)
from roadmap.config.settings import settings
from roadmap.storage.database import create_all_tables, get_session
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.progress_repository import SqliteProgressRepository
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository
from roadmap.storage.repositories.skill_repository import SqliteSkillRepository


def initialize_database() -> None:
    """Ensure the data directory and all DB tables exist."""
    settings.ensure_data_dir()
    create_all_tables()


@contextmanager
def get_profile_use_cases() -> Generator[
    tuple[CreateProfileUseCase, GetProfileUseCase, UpdateProfileUseCase], None, None
]:
    """Yield profile use cases bound to a database session."""
    with get_session() as session:
        repo = SqliteProfileRepository(session)
        yield (
            CreateProfileUseCase(repo),
            GetProfileUseCase(repo),
            UpdateProfileUseCase(repo),
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
