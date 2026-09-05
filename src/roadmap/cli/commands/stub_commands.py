"""
Stub commands for MVP-2+ features.

These commands exist in MVP-1 so the CLI is complete and user-friendly,
but they show a clear "not yet available" message rather than crashing.
"""

from __future__ import annotations

import typer

from roadmap.cli.display.console import print_info, print_warning

# ── research ──────────────────────────────────────────────────────────────────
research_app = typer.Typer()


@research_app.command()
def research(
    refresh: bool = typer.Option(False, "--refresh", help="Force re-research"),
) -> None:
    """Research market requirements and learning resources. [MVP-3]"""
    print_warning("Market research requires MVP-3 (Exa search integration).")
    print_info("This feature will be available in MVP-3.")
    print_info("Run [bold]roadmap generate[/bold] for LLM-based generation (MVP-2).")
    raise typer.Exit(0)





# ── complete ──────────────────────────────────────────────────────────────────
complete_app = typer.Typer()


@complete_app.command()
def complete(
    skill: str = typer.Argument(help="Skill name to mark as complete"),
) -> None:
    """Mark a skill as complete. [MVP-5]"""
    print_warning("Skill completion tracking requires MVP-5.")
    print_info(f"Skill: [bold]{skill}[/bold]")
    raise typer.Exit(0)


# ── update ────────────────────────────────────────────────────────────────────
update_app = typer.Typer()


@update_app.command()
def update() -> None:
    """Replan roadmap based on current progress. [MVP-5]"""
    print_warning("Adaptive replanning requires MVP-5.")
    raise typer.Exit(0)


# ── why ───────────────────────────────────────────────────────────────────────
why_app = typer.Typer()


@why_app.command()
def why(
    skill: str = typer.Argument(help="Skill name to explain"),
) -> None:
    """Explain why a skill is included, postponed, or excluded. [MVP-5]"""
    print_warning("Recommendation explanations require MVP-5.")
    print_info(f"Skill: [bold]{skill}[/bold]")
    raise typer.Exit(0)


# ── sources ───────────────────────────────────────────────────────────────────
sources_app = typer.Typer()


@sources_app.command()
def sources() -> None:
    """List all research sources. [MVP-3]"""
    print_warning("Research sources require MVP-3 (Exa search integration).")
    raise typer.Exit(0)


# ── export ────────────────────────────────────────────────────────────────────
export_app = typer.Typer()


@export_app.command()
def export(
    format: str = typer.Option("markdown", "--format", "-f", help="json | markdown"),
) -> None:
    """Export the roadmap as JSON or Markdown. [MVP-6]"""
    print_warning("Roadmap export requires MVP-6.")
    raise typer.Exit(0)
