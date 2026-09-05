"""
SQLAlchemy database engine and session factory.

Supports SQLite (development) and PostgreSQL (production) via
a single DATABASE_URL setting.

SQLite-specific config:
  - WAL mode for better concurrency
  - Foreign key enforcement (disabled by default in SQLite)
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from roadmap.config.settings import settings
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the singleton SQLAlchemy engine, creating it if needed."""
    global _engine
    if _engine is None:
        db_url = settings.resolved_database_url
        logger.info("Creating database engine", url=_sanitize_url(db_url))

        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            db_url,
            connect_args=connect_args,
            echo=(settings.log_level == "DEBUG"),
        )

        # SQLite-specific setup
        if db_url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:  # noqa: ARG001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the singleton session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autoflush=True,
            expire_on_commit=False,
        )
    return _SessionFactory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager that yields a database session with auto-commit/rollback."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables() -> None:
    """Create all tables defined in the ORM models."""
    import roadmap.storage.models  # noqa: F401
    from roadmap.storage.models.base import Base  # noqa: F401  (imports all models)

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")


def _sanitize_url(url: str) -> str:
    """Remove passwords from DB URL for logging."""
    if "@" in url:
        scheme = url.split("://")[0]
        rest = url.split("@")[-1]
        return f"{scheme}://***@{rest}"
    return url
