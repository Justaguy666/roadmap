"""
Request logging and request-ID middleware for RoadmapAI API.

Every request gets a unique X-Request-ID header (echoed in response).
Structured log entries include: request_id, method, path, status_code, duration_ms.

NEVER logs: API keys, auth credentials, full request bodies.
Authentication: NOT YET IMPLEMENTED — deferred to MVP-7.3.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Generates or propagates X-Request-ID for each request.
    2. Logs structured request/response metadata via structlog.
    3. Adds X-Request-ID to the response headers.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:  # type: ignore[override]
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        start = time.perf_counter()

        response: Response = await call_next(request)  # type: ignore[operator]

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id

        logger.info(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response
