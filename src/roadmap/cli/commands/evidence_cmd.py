"""
CLI command: `roadmap evidence <skill>`

Displays aggregated research citations, weighted scores, frequency, and source reliability for a specific skill.
"""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from roadmap.cli.container import initialize_database
from roadmap.cli.display.console import console, print_header, print_info, print_warning
from roadmap.domain.services.evidence_aggregator import EvidenceAggregator
from roadmap.storage.database import get_session
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteSourceRepository,
)

evidence_app = typer.Typer(help="Inspect aggregated research evidence for a specific skill.")


@evidence_app.callback(invoke_without_command=True)
def show_evidence(
    skill: str = typer.Argument(help="Skill name to look up evidence for"),
) -> None:
    """Show aggregated evidence, weighted reliability score, and citations for a skill."""
    initialize_database()

    with get_session() as session:
        evidence_repo = SqliteEvidenceRepository(session)
        source_repo = SqliteSourceRepository(session)

        evidence_items = evidence_repo.find_by_skill(skill)
        if not evidence_items:
            print_warning(f"No research evidence records found for skill: '[bold]{skill}[/bold]'.")
            print_info("Run [bold]roadmap research[/bold] to gather market intelligence and source claims.")
            raise typer.Exit(0)

        all_sources = source_repo.list_all(limit=500)
        sources_by_id = {s.id: s for s in all_sources}

        summary = EvidenceAggregator.aggregate_for_skill(
            skill_name=skill,
            evidence_items=evidence_items,
            sources_by_id=sources_by_id,
        )

        print_header(f"Research Evidence Summary: {skill}")

        score_color = "green" if summary.weighted_score >= 0.70 else "yellow" if summary.weighted_score >= 0.40 else "red"

        console.print(
            Panel(
                f"[bold white]Skill:[/bold white] [bold cyan]{summary.skill_name}[/bold cyan]\n"
                f"[bold white]Composite Weighted Score:[/bold white] [{score_color}]{summary.weighted_score:.3f} / 1.000[/{score_color}]\n"
                f"[bold white]Evidence Count:[/bold white] {summary.evidence_count} claims from {summary.unique_source_count} unique sources\n"
                f"[bold white]Avg Relevance:[/bold white] {int(summary.average_relevance * 100)}%  |  "
                f"[bold white]Avg Confidence:[/bold white] {int(summary.average_confidence * 100)}%  |  "
                f"[bold white]Avg Reliability:[/bold white] {int(summary.average_reliability * 100)}%\n"
                f"[bold white]Freshness Factor:[/bold white] {summary.freshness_factor:.2f}\n"
                f"[bold white]Publisher Domains:[/bold white] {', '.join(summary.supporting_domains) if summary.supporting_domains else 'General Web'}",
                title="Evidence Quality Assessment",
                border_style="cyan",
            )
        )

        if summary.divergence_notes:
            console.print()
            for note in summary.divergence_notes:
                print_warning(note)

        console.print()
        table = Table(title="Supporting Extracted Claims & Citations", border_style="cyan")
        table.add_column("Evidence ID", style="dim", width=10)
        table.add_column("Source / Publisher", style="bold white", width=22)
        table.add_column("Type", justify="center", width=14)
        table.add_column("Score", justify="center", width=8)
        table.add_column("Extracted Claim")

        for ev in evidence_items:
            src = sources_by_id.get(ev.source_id)
            pub = src.domain or src.publisher or "web" if src else "web"
            stype = src.source_type.value if src else "other"
            rel = f"{int(ev.relevance * 100)}%"
            table.add_row(
                ev.id[:8],
                pub[:20],
                stype.upper(),
                rel,
                ev.extracted_claim,
            )

        console.print(table)
        console.print()
        print_info("Run [bold]roadmap why <skill>[/bold] to see how these citations directly influenced planning.")
        console.print()
