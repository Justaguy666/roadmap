"""
Stub commands for MVP-2+ features.

These commands exist in MVP-1 so the CLI is complete and user-friendly,
but they show a clear "not yet available" message rather than crashing.
"""

from __future__ import annotations

from typing import Any

import typer

from roadmap.cli.display.console import console, print_info, print_warning

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
    """Explain why a skill is included, prioritized, or postponed."""
    from rich.panel import Panel
    from rich.table import Table

    from roadmap.cli.container import initialize_database
    from roadmap.storage.database import get_session
    from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
    from roadmap.storage.repositories.research_repository import (
        SqliteEvidenceRepository,
        SqliteRecommendationRepository,
        SqliteSourceRepository,
    )
    from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository

    initialize_database()
    with get_session() as session:
        profile_repo = SqliteProfileRepository(session)
        roadmap_repo = SqliteRoadmapRepository(session)
        rec_repo = SqliteRecommendationRepository(session)
        ev_repo = SqliteEvidenceRepository(session)
        src_repo = SqliteSourceRepository(session)

        profile = profile_repo.load()
        if not profile:
            print_warning("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        roadmap = roadmap_repo.load_latest(profile.id)
        if not roadmap:
            print_warning("No roadmap found. Run `roadmap generate` first.")
            raise typer.Exit(1)

        rec = rec_repo.find_by_skill_name_or_id(skill, roadmap_id=roadmap.id)
        if not rec:
            # Fallback search across any roadmap
            rec = rec_repo.find_by_skill_name_or_id(skill)

        if not rec:
            print_warning(f"No explicit decision factors found for skill: '[bold]{skill}[/bold]'.")
            print_info("Try running [bold]roadmap generate[/bold] to evaluate and score this skill.")
            raise typer.Exit(0)

        # Render Decision Summary
        action_style = "bold green" if rec.decision == "include" else "bold yellow"
        raw_factors = rec.decision_factors
        factors: dict[str, Any] = raw_factors if isinstance(raw_factors, dict) else {}

        console.print()
        console.print(
            Panel(
                f"[bold white]Skill:[/bold white] [bold cyan]{skill}[/bold cyan]\n"
                f"[bold white]Decision:[/bold white] [{action_style}]{rec.decision.upper()}[/{action_style}]\n"
                f"[bold white]Confidence:[/bold white] {int(rec.confidence * 100)}%\n\n"
                f"[bold white]Rationale:[/bold white] {rec.reasoning}",
                title=f"Decision Explanation: {skill}",
                border_style="cyan",
            )
        )

        if factors:
            factor_table = Table(title="Decision Factor Breakdown (Weights & Signals)", border_style="cyan")
            factor_table.add_column("Factor Dimension", style="bold white")
            factor_table.add_column("Factor Score", justify="center")
            factor_table.add_column("Description / Interpretation")

            factor_table.add_row(
                "Market Relevance",
                f"{int(float(factors.get('market_relevance', 0.0)) * 100)}%",
                "Observed frequency in job postings and industry hiring profiles",
            )
            factor_table.add_row(
                "Goal Relevance",
                f"{int(float(factors.get('goal_relevance', 0.0)) * 100)}%",
                "Direct contribution to target career competencies",
            )
            factor_table.add_row(
                "Skill Gap",
                f"{int(float(factors.get('skill_gap', 0.0)) * 100)}%",
                "Distance from current reported level to target proficiency",
            )
            factor_table.add_row(
                "Prerequisite Importance",
                f"{int(float(factors.get('prerequisite_importance', 0.0)) * 100)}%",
                "Number of downstream roadmap skills depending on this competency",
            )
            factor_table.add_row(
                "Portfolio Value",
                f"{int(float(factors.get('portfolio_value', 0.0)) * 100)}%",
                "Tangible proof and project demonstrable impact",
            )
            factor_table.add_row(
                "Time Cost Factor",
                f"{int(float(factors.get('time_cost_factor', 0.0)) * 100)}%",
                "Feasibility of acquisition within user's weekly study budget",
            )
            console.print(factor_table)

        if rec.evidence_ids:
            console.print()
            console.print(f"  [bold]Supporting Evidence Citations ({len(rec.evidence_ids)}):[/bold]")
            for eid in rec.evidence_ids[:5]:
                ev = ev_repo.get_by_id(eid)
                if ev:
                    src = src_repo.get_by_id(ev.source_id)
                    domain = src.domain if src else "web"
                    console.print(f"  [dim]•[/dim] [cyan]{domain}[/cyan]: \"{ev.extracted_claim[:80]}...\" [dim](conf: {int(ev.confidence*100)}%)[/dim]")
            console.print()


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
