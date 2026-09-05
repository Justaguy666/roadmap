"""
Pytest configuration and shared fixtures.

Uses an in-memory SQLite database for integration tests.
All tests run in isolation — no shared state between test functions.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from roadmap.storage.models import Base


@pytest.fixture(scope="function")
def sqlite_engine():
    """Create an in-memory SQLite engine for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # Enable FK enforcement for SQLite
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_pragmas(dbapi_conn, record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(sqlite_engine):
    """Yield a database session that is rolled back after each test."""
    Session = sessionmaker(bind=sqlite_engine, autoflush=True, autocommit=False)
    session = Session()
    yield session
    session.rollback()
    session.close()
