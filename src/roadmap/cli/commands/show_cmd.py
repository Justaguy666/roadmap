"""
CLI command: `roadmap show [--phase N]`

Displays the current roadmap overview or a specific phase.
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from roadmap.cli.container import get_roadmap_context, initialize_database
from roadmap.cli.display.console import console, print_error, print_header, print_info
from roadmap.cli.display.tables import render_phase_detail, render_roadmap_overview
from roadmap.domain.exceptions import ProfileNotFoundError, RoadmapNotFoundError

app = typer.Typer()


@app.command()
def show(
    phase: Annotated[
        Optional[int],
        typer.Option("--phase", "-p", help="Show details for a specific phase number"),
    ] = None,
) -> None:
    """Display the current roadmap."""
    initialize_database()

    with get_roadmap_context() as (profile_repo, skill_repo, roadmap_repo, progress_repo):
        profile = profile_repo.load()
        if profile is None:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        roadmap = roadmap_repo.load_latest(profile.id)
        if roadmap is None:
            print_info(
                "No roadmap yet. Run [bold]roadmap generate[/bold] to create one.\n"
                "  [dim](MVP-1: basic generation without LLM is planned next)[/dim]"
            )
            raise typer.Exit(0)

        # Build progress map
        records = progress_repo.load_all(profile.id)
        progress_map = {r.skill_id: r.completion_percentage for r in records}

        if phase is not None:
            # Show a specific phase
            matching = [p for p in roadmap.phases if p.phase_number == phase]
            if not matching:
                print_error(f"Phase {phase} not found in roadmap.")
                raise typer.Exit(1)
            selected_phase = matching[0]
            print_header(f"Phase {selected_phase.phase_number} — {selected_phase.name}")
            if selected_phase.objective:
                console.print(f"  [dim]{selected_phase.objective}[/dim]")
                console.print()
            render_phase_detail(selected_phase)
            console.print()
        else:
            # Show overview
            print_header(f"{roadmap.title}")
            render_roadmap_overview(roadmap, progress_map)
            console.print()
            console.print(
                "  [dim]Run [bold]roadmap show --phase N[/bold] for phase details.[/dim]"
            )
            console.print()
