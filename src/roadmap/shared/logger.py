"""
Structured logging configuration using structlog.

Every log entry includes:
- timestamp (ISO 8601)
- log level
- logger name
- workflow_id / run_id when set via contextvars
- message

NEVER log API keys, passwords, or personal user data.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# Context variables — set these at the start of a workflow
_workflow_id: ContextVar[str] = ContextVar("workflow_id", default="")
_run_id: ContextVar[str] = ContextVar("run_id", default="")
_agent: ContextVar[str] = ContextVar("agent", default="")


def set_workflow_context(
    workflow_id: str = "",
    run_id: str = "",
    agent: str = "",
) -> None:
    """Bind context variables for the current async/thread context."""
    _workflow_id.set(workflow_id)
    _run_id.set(run_id)
    _agent.set(agent)


def _add_context_fields(
    logger: Any,  # noqa: ANN401
    method: str,  # noqa: ARG001
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Processor: inject context variables into every log record."""
    if wid := _workflow_id.get():
        event_dict["workflow_id"] = wid
    if rid := _run_id.get():
        event_dict["run_id"] = rid
    if agent := _agent.get():
        event_dict["agent"] = agent
    return event_dict


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """
    Set up structlog.

    Args:
        level: Standard Python log level string (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, emit JSON lines (for production/log aggregators).
                     If False, emit human-friendly colored output.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_context_fields,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *shared_processors,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to *name*."""
    return structlog.get_logger(name)  # type: ignore[return-value]
