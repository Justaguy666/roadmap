"""CLI command: `roadmap progress`"""

from __future__ import annotations

import typer

from roadmap.cli.container import get_roadmap_context, initialize_database
from roadmap.cli.display.console import console, print_error, print_header, print_info
from roadmap.cli.display.tables import render_progress_dashboard
from roadmap.domain.services.progress_tracker import ProgressTracker

app = typer.Typer()


@app.command()
def progress() -> None:
    """Show overall learning progress across all phases."""
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

        records = progress_repo.load_all(profile.id)
        progress_map = {r.skill_id: r.completion_percentage for r in records}

        tracker = ProgressTracker()
        computed = tracker.compute_roadmap_progress(roadmap, progress_map)

        print_header(f"Progress — {roadmap.title}")
        render_progress_dashboard(roadmap, progress_map)

        overall = computed.get("overall", 0.0)
        completed_phases = len(roadmap.completed_phases)
        total_phases = len(roadmap.phases)
        total_skills = len(roadmap.all_skills)
        completed_skills = sum(
            1 for s in roadmap.all_skills
            if progress_map.get(s.id, 0.0) >= 100.0
        )

        console.print(
            f"  Overall: [bold]{overall:.1f}%[/bold]  "
            f"([dim]{completed_skills}/{total_skills} skills, "
            f"{completed_phases}/{total_phases} phases[/dim])"
        )
        console.print()

        current = roadmap.current_phase
        if current:
            console.print(
                f"  Current phase: [highlight]Phase {current.phase_number} — {current.name}[/highlight]"
            )
            console.print()
