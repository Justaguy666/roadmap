"""
Application entry point.

Configures logging then delegates to the Typer CLI app.
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

from roadmap.cli.app import app
from roadmap.config.settings import settings
from roadmap.shared.logger import configure_logging


def main() -> None:
    configure_logging(
        level=settings.log_level,
        json_output=(settings.env == "production"),
    )
    app()


if __name__ == "__main__":
    main()
