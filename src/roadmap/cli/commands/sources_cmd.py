"""
CLI command: roadmap sources [--skill <name>].

Lists evidence sources and claims supporting the roadmap recommendations.
"""

from __future__ import annotations

import typer
from rich.table import Table

from roadmap.cli.container import get_research_context, initialize_database
from roadmap.cli.display.console import console, print_info, print_warning

sources_app = typer.Typer(help="Inspect research sources and citations.")


@sources_app.callback(invoke_without_command=True)
def list_sources(
    skill: str | None = typer.Option(None, "--skill", "-s", help="Filter sources by associated skill"),
) -> None:
    """List all research sources analyzed by the system."""
    initialize_database()
    with get_research_context() as (_, source_repo, evidence_repo, _, _):
        if skill:
            evidence_items = evidence_repo.find_by_skill(skill)
            if not evidence_items:
                print_warning(f"No evidence found for skill: [bold]{skill}[/bold]")
                raise typer.Exit(0)

            table = Table(
                title=f"Evidence & Sources for Skill: [bold cyan]{skill}[/bold cyan]",
                border_style="cyan",
            )
            table.add_column("Evidence ID", style="dim")
            table.add_column("Extracted Claim", style="white")
            table.add_column("Relevance", justify="center")
            table.add_column("Confidence", justify="center")
            table.add_column("Source Domain")

            for ev in evidence_items:
                src = source_repo.get_by_id(ev.source_id)
                domain = src.domain if src else "unknown"
                table.add_row(
                    ev.id[:8],
                    ev.extracted_claim[:70] + "...",
                    f"{int(ev.relevance * 100)}%",
                    f"{int(ev.confidence * 100)}%",
                    domain,
                )
            console.print(table)
            return

        sources = source_repo.list_all(limit=50)
        if not sources:
            print_warning("No sources found. Run [bold]roadmap research[/bold] first.")
            raise typer.Exit(0)

        table = Table(title="Research Evidence Sources", border_style="cyan")
        table.add_column("Domain / Publisher", style="bold white")
        table.add_column("Type", justify="center")
        table.add_column("Reliability Score", justify="center", style="green")
        table.add_column("Title / URL")

        for s in sources:
            rel_pct = f"{int(s.reliability_score * 100)}%"
            title_disp = s.title if s.title else s.url
            if len(title_disp) > 55:
                title_disp = title_disp[:52] + "..."
            table.add_row(
                s.domain or s.publisher or "web",
                s.source_type.value.upper(),
                rel_pct,
                title_disp,
            )
        console.print(table)
        print_info(f"Showing {len(sources)} source(s). Use [bold]roadmap sources --skill <name>[/bold] for skill citations.")
