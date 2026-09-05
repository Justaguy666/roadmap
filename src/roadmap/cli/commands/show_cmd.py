"""
CLI command: `roadmap show [--phase N] [--all]`

Displays the current roadmap overview or detailed phase curriculum.
"""

from __future__ import annotations

from typing import Annotated

import typer

from roadmap.cli.container import get_roadmap_context, initialize_database
from roadmap.cli.display.console import console, print_error, print_header, print_info
from roadmap.cli.display.tables import render_phase_detail, render_roadmap_overview

app = typer.Typer()


@app.command()
def show(
    phase: Annotated[
        int | None,
        typer.Option("--phase", "-p", help="Show full details for a specific phase number"),
    ] = None,
    all_phases: Annotated[
        bool,
        typer.Option("--all", "-a", help="Show full details for all roadmap phases"),
    ] = False,
) -> None:
    """Display the current roadmap."""
    initialize_database()

    with get_roadmap_context() as (profile_repo, _, roadmap_repo, progress_repo):
        profile = profile_repo.load()
        if profile is None:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        roadmap = roadmap_repo.load_latest(profile.id)
        if roadmap is None:
            print_info(
                "No roadmap yet. Run [bold]roadmap generate[/bold] to create one."
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
            console.print(f"  Duration: [bold]{selected_phase.estimated_weeks:.0f} weeks[/bold]")
            if selected_phase.objective:
                console.print(f"  Objective: [dim]{selected_phase.objective}[/dim]")
            console.print()
            render_phase_detail(selected_phase)
            console.print()
        elif all_phases:
            # Show all phases in sequence
            print_header(f"{roadmap.title}")
            for p in roadmap.phases:
                console.print()
                console.print(f"  [bold highlight]Phase {p.phase_number} — {p.name}[/bold highlight]")
                console.print(f"  Duration: [bold]{p.estimated_weeks:.0f} weeks[/bold]")
                if p.objective:
                    console.print(f"  Objective: [dim]{p.objective}[/dim]")
                console.print()
                render_phase_detail(p)
            console.print()
        else:
            # Show overview
            print_header(f"{roadmap.title.upper()}")
            console.print(f"  Target: [bold]{profile.target_role or profile.target_goal}[/bold]")
            console.print()
            render_roadmap_overview(roadmap, progress_map)
            console.print()

            # Compact phase summaries
            for p in roadmap.phases:
                console.print(f"  [bold]Phase {p.phase_number} — {p.name}[/bold] [dim]({p.estimated_weeks:.0f} weeks)[/dim]")
                skill_preview = ", ".join(s.name for s in p.skills[:5])
                if len(p.skills) > 5:
                    skill_preview += f" [dim]+{len(p.skills) - 5} more[/dim]"
                console.print(f"    [dim]Skills:[/dim] {skill_preview}")
                if p.projects:
                    console.print(f"    [dim]Project:[/dim] [info]{p.projects[0].name}[/info]")
                if p.milestones and p.milestones[0].exit_criteria:
                    console.print(f"    [dim]Exit Criteria:[/dim] {p.milestones[0].exit_criteria[0]}")
                console.print()

            console.print(
                "  [dim]Run [bold]roadmap show --phase N[/bold] or [bold]roadmap show --all[/bold] for full curriculum.[/dim]"
            )
            console.print()
