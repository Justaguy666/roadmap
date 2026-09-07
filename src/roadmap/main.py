"""
Application entry point.

Configures logging then delegates to the Typer CLI app.

Commands:
  roadmap <cmd>   - CLI interface (default)
  roadmap api     - Start the FastAPI HTTP server (same ASGI app as roadmap.api.main:app)
"""

from __future__ import annotations

import os
import sys

# Ensure UTF-8 output on all platforms (especially Windows)
os.environ.setdefault("PYTHONUTF8", "1")
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except AttributeError:
        pass

import typer

from roadmap.cli.app import app
from roadmap.config.settings import settings
from roadmap.shared.logger import configure_logging


@app.command(name="api", help="Start the RoadmapAI HTTP API server (FastAPI/uvicorn).")
def api_server(
    host: str = typer.Option(None, "--host", "-H", help="Bind host (default: ROADMAP_API_HOST)"),
    port: int = typer.Option(None, "--port", "-p", help="Bind port (default: ROADMAP_API_PORT)"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload (development only)"),
) -> None:
    """Launch the FastAPI HTTP server using the canonical roadmap.api.main:app ASGI application."""
    import uvicorn

    bind_host = host or settings.api_host
    bind_port = port or settings.api_port

    configure_logging(
        level=settings.log_level,
        json_output=(settings.env == "production"),
    )

    uvicorn.run(
        "roadmap.api.main:app",
        host=bind_host,
        port=bind_port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


def main() -> None:
    configure_logging(
        level=settings.log_level,
        json_output=(settings.env == "production"),
    )
    app()


if __name__ == "__main__":
    main()
