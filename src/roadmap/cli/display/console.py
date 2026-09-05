"""
Rich console singleton and helper utilities.

All CLI output goes through this module.
Never use print() directly in command handlers.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager

from rich.console import Console
from rich.theme import Theme

# Force UTF-8 output on Windows to support Unicode symbols
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except AttributeError:
        pass

ROADMAP_THEME = Theme({
    "info": "dim cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "highlight": "bold cyan",
    "dim": "dim",
    "phase_done": "bold green",
    "phase_active": "bold yellow",
    "phase_pending": "dim white",
    "skill_done": "green",
    "skill_progress": "yellow",
    "skill_pending": "dim",
    "critical": "bold red",
    "high": "bold yellow",
    "medium": "cyan",
    "low": "dim",
})

# Singleton console
console = Console(theme=ROADMAP_THEME, highlight=False)
err_console = Console(stderr=True, theme=ROADMAP_THEME)


def print_success(message: str) -> None:
    console.print(f"  [success]✓[/success] {message}")


def print_error(message: str) -> None:
    err_console.print(f"  [error]✗[/error] {message}")


def print_warning(message: str) -> None:
    console.print(f"  [warning]⚠[/warning] {message}")


def print_info(message: str) -> None:
    console.print(f"  [info]·[/info] {message}")


def print_header(title: str) -> None:
    console.print()
    console.print(f"  [highlight]{title}[/highlight]")
    console.print(f"  {'─' * len(title)}", style="dim")
    console.print()


def print_section(title: str) -> None:
    console.print()
    console.print(f"  [bold]{title}[/bold]")


def print_rule(title: str = "") -> None:
    from rich.rule import Rule
    if title:
        console.print(Rule(f"  {title}  ", style="dim"))
    else:
        console.print(Rule(style="dim"))


@contextmanager
def spin(message: str) -> Generator[None, None, None]:
    """Context manager that shows a spinner while work is in progress."""
    from rich.live import Live
    from rich.spinner import Spinner
    spinner = Spinner("dots", text=f"  {message}", style="cyan")
    with Live(spinner, console=console, refresh_per_second=10):
        yield
