"""
API test fixtures.

Uses an in-memory SQLite database for ALL API tests.
The production roadmap.db is NEVER touched by API tests.

IMPORTANT: SQLite :memory: databases are per-connection. We use StaticPool
to ensure all sessions share the SAME single connection (and thus the same
in-memory database with all tables).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from roadmap.api.dependencies import (
    get_db_session,
    get_embedding_provider,
    get_llm_provider,
)
from roadmap.api.main import app
from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.storage.database import reset_engine
from roadmap.storage.models import Base


@pytest.fixture(autouse=True)
def isolate_database_url(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure all global settings and engines point to :memory: during API tests."""
    from roadmap.config.settings import settings

    monkeypatch.setattr(settings, "database_url", "sqlite:///:memory:")
    reset_engine()
    yield
    reset_engine()


@pytest.fixture(scope="function")
def test_engine():
    """
    Isolated in-memory SQLite engine, per test function.

    Uses StaticPool so ALL sessions share the SAME single connection.
    This is required because SQLite :memory: creates a separate empty
    database for each new connection — StaticPool prevents that.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Critical: all sessions share one connection
    )

    @event.listens_for(engine, "connect")
    def set_pragmas(dbapi_conn, record):  # noqa: ARG001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def api_client(test_engine) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient with dependency overrides.

    - database session -> per-request session from isolated in-memory engine
    - embedding provider -> FakeEmbeddingProvider (no real embeddings)
    - llm provider -> FakeLLMProvider (no real LLM calls)
    """
    test_session_factory = sessionmaker(bind=test_engine, autoflush=True, autocommit=False)

    def override_session() -> Generator[Session, None, None]:
        """Create a fresh session for each request, sharing the same single connection."""
        session: Session = test_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider()

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()
