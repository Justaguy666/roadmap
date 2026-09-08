"""
RoadmapAI FastAPI ASGI application (MVP-7.2).

Architecture:
  HTTP
   |
   v
  FastAPI Router          (api/routers/)
   |
   v
  Request DTO (Pydantic)  (api/schemas/)
   |
   v
  Application Use Case    (application/use_cases/, application/services/)
   |
   v
  Domain                  (domain/)
   |
   v
  Repository Port         (application/ports/repositories.py)
   |
   v
  Infrastructure          (storage/repositories/)

IMPORTANT:
- This is the SINGLE canonical ASGI application object.
- The `roadmap api` CLI command points to this same object.
- Do NOT create a second application init path.

Authentication: NOT YET IMPLEMENTED.
This is an explicit MVP-7.3 concern. All endpoints are currently unauthenticated.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from roadmap.api.middleware import RequestLoggingMiddleware
from roadmap.api.routers import (
    adaptations,
    auth,
    feedback,
    health,
    knowledge,
    profiles,
    progress,
    roadmaps,
)
from roadmap.application.ports.embedding_provider import EmbeddingProviderError
from roadmap.application.ports.llm_provider import MissingAPIKeyError
from roadmap.config.settings import settings
from roadmap.shared.logger import configure_logging, get_logger

logger = get_logger(__name__)

_API_VERSION = "v1"
_API_TITLE = "RoadmapAI API"
_API_DESCRIPTION = (
    "Production API adapter for RoadmapAI — AI-powered adaptive learning and career roadmap agent.\n\n"
    "## Architecture\n"
    "The API is a thin adapter layer over the existing Application Use Cases. "
    "All business logic (generation, validation, adaptation, knowledge retrieval) "
    "is implemented in the application layer and is shared with the CLI.\n\n"
    "## Authentication & Authorization\n"
    "Multi-user identity and authorization implemented (MVP-7.3).\n"
    "- Register: `POST /api/v1/auth/register`\n"
    "- Login: `POST /api/v1/auth/login`\n"
    "- Current User: `GET /api/v1/auth/me`\n"
    "All profile and roadmap resources are protected with Bearer JWT tokens.\n\n"
    "## Versioning\n"
    "All resource endpoints are prefixed with `/api/v1/`.\n"
)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan: initialise database on startup.

    Reuses the existing infrastructure — does NOT create a second engine.
    """
    configure_logging(
        level=settings.log_level,
        json_output=(settings.env == "production"),
    )
    logger.info(
        "RoadmapAI API starting",
        version=_API_VERSION,
        env=settings.env,
        db=settings.resolved_database_url.split("///")[-1] if "///" in settings.resolved_database_url else "configured",
    )
    settings.ensure_data_dir()
    if settings.env != "production":
        from roadmap.storage.database import create_all_tables

        create_all_tables()
    else:
        logger.info("Production mode: schema managed via Alembic migrations ('alembic upgrade head')")

    yield

    logger.info("RoadmapAI API shutting down")


app = FastAPI(
    title=_API_TITLE,
    description=_API_DESCRIPTION,
    version="7.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(RequestLoggingMiddleware)

if settings.api_cors_origins:
    # Only enable CORS when explicitly configured — never unrestricted
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=False,  # Credentials require authentication; not implemented yet
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def _error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Convert HTTPException to canonical error envelope."""
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        # Already wrapped by a router
        return JSONResponse(status_code=exc.status_code, content=detail)
    return _error_response("HTTP_ERROR", str(detail), exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert Pydantic validation errors to canonical error envelope."""
    errors = exc.errors()
    # Summarise without exposing internal paths
    summary = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
        for e in errors
    )
    return _error_response("VALIDATION_ERROR", summary, 422)


@app.exception_handler(EmbeddingProviderError)
async def embedding_provider_error_handler(request: Request, exc: EmbeddingProviderError) -> JSONResponse:
    logger.error("Embedding provider error", path=request.url.path, exc_type=type(exc).__name__)
    return _error_response("PROVIDER_ERROR", "Embedding provider is unavailable", 503)


@app.exception_handler(MissingAPIKeyError)
async def missing_api_key_error_handler(request: Request, exc: MissingAPIKeyError) -> JSONResponse:
    logger.error("Missing API key error", path=request.url.path, provider=exc.provider)
    return _error_response("PROVIDER_ERROR", f"Configuration error: missing API key for {exc.provider}", 503)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all: log the error, return 500 without exposing internals.

    Never exposes: stack traces, API keys, SQL errors, internal file paths.
    """
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        exc_type=type(exc).__name__,
        # Do NOT log exc details that may contain sensitive info
    )
    return _error_response("INTERNAL_ERROR", "An unexpected error occurred", 500)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Health probes — no prefix, no versioning (infra probes must be stable)
app.include_router(health.router)

# Versioned resource routes
prefix = settings.api_prefix

app.include_router(auth.router, prefix=prefix)
app.include_router(profiles.router, prefix=prefix)
app.include_router(roadmaps.router, prefix=prefix)
app.include_router(progress.router, prefix=prefix)
app.include_router(feedback.router, prefix=prefix)
app.include_router(adaptations.router, prefix=prefix)
app.include_router(knowledge.router, prefix=prefix)
