from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from roadmap.api.dependencies import get_db_session
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Liveness check",
    description="Returns ok immediately. Does not touch the database or external providers.",
    response_description="Service is alive",
)
def health() -> dict[str, str]:
    """Liveness probe — cheap and deterministic."""
    return {"status": "ok"}


@router.get(
    "/health/readiness",
    summary="Readiness check",
    description=(
        "Verifies the application is initialised and the database is reachable. "
        "Does NOT call Gemini, Exa, or any embedding provider. "
        "Does NOT consume LLM budget."
    ),
    response_description="Service readiness status",
)
def readiness(
    response: Response,
    session: Session = Depends(get_db_session),
) -> dict[str, str]:
    """
    Readiness probe.

    Checks:
    - Database session is reachable (simple SELECT 1).

    Does NOT check:
    - LLM provider availability
    - Exa search availability
    - Embedding provider
    """
    try:
        session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.error("Readiness check database failure", exc_info=str(exc))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "unavailable"}

    return {"status": "ready", "database": db_status}

