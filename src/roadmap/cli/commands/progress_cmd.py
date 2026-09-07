"""CLI commands for learning progress tracking: `roadmap progress` and `roadmap progress update`."""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from roadmap.application.use_cases.record_progress import UpdateProgressUseCase
from roadmap.cli.container import get_progress_context, initialize_database
from roadmap.cli.display.console import console, print_error, print_header, print_info, print_success
from roadmap.cli.display.tables import render_progress_dashboard
from roadmap.domain.entities.adaptation import DeviationStatus
from roadmap.domain.entities.progress_record import ProgressStatus
from roadmap.domain.services.deviation_detector import DeviationDetector
from roadmap.domain.services.progress_tracker import ProgressTracker

progress_app = typer.Typer(help="Track and record learning progress.")


@progress_app.callback(invoke_without_command=True)
def progress(ctx: typer.Context) -> None:
    """Show overall learning progress, skill completion, and schedule health."""
    if ctx.invoked_subcommand is not None:
        return

    initialize_database()

    with get_progress_context() as (profile_repo, roadmap_repo, progress_repo, feedback_repo, _):
        profile = profile_repo.load()
        if profile is None:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        roadmap = roadmap_repo.load_latest(profile.id)
        if roadmap is None:
            print_info("No roadmap yet. Run [bold]roadmap generate[/bold] to create one.")
            raise typer.Exit(0)

        records = progress_repo.load_all(profile.id)
        record_map = {r.skill_id: r for r in records}
        progress_map = {r.skill_id: r.completion_percentage for r in records}

        tracker = ProgressTracker()
        computed = tracker.compute_roadmap_progress(roadmap, progress_map)

        print_header(f"Progress — {roadmap.title} (v{roadmap.version})")
        render_progress_dashboard(roadmap, progress_map)

        overall = computed.get("overall", 0.0)
        completed_phases = len(roadmap.completed_phases)
        total_phases = len(roadmap.phases)
        total_skills = len(roadmap.all_skills)
        completed_skills = sum(
            1 for s in roadmap.all_skills if progress_map.get(s.id, 0.0) >= 100.0
        )

        console.print(
            f"  Overall: [bold]{overall:.1f}%[/bold]  "
            f"([dim]{completed_skills}/{total_skills} skills, "
            f"{completed_phases}/{total_phases} phases[/dim])"
        )
        console.print()

        # Render Skills Progress Table
        table = Table(title="Tracked Skills Progress", border_style="dim")
        table.add_column("Phase", justify="center", style="dim")
        table.add_column("Skill Name", style="bold white")
        table.add_column("Status", justify="center")
        table.add_column("Progress", justify="right")
        table.add_column("Planned", justify="right", style="dim")
        table.add_column("Actual", justify="right")
        table.add_column("Notes", style="dim")

        for phase in roadmap.phases:
            for skill in phase.skills:
                rec = record_map.get(skill.id)
                status_str = rec.status.value if rec else "NOT_STARTED"
                pct = rec.completion_percentage if rec else 0.0
                actual_h = rec.actual_hours if rec else 0.0
                notes_str = (rec.notes[:30] + "...") if (rec and len(rec.notes) > 30) else (rec.notes if rec else "")

                if status_str == "COMPLETED" or pct >= 100.0:
                    status_badge = "[green]COMPLETED[/green]"
                elif status_str == "BLOCKED":
                    status_badge = "[bold red]BLOCKED[/bold red]"
                elif status_str == "IN_PROGRESS":
                    status_badge = "[cyan]IN_PROGRESS[/cyan]"
                elif status_str == "SKIPPED":
                    status_badge = "[dim]SKIPPED[/dim]"
                else:
                    status_badge = "[dim]NOT_STARTED[/dim]"

                table.add_row(
                    f"P{phase.phase_number}",
                    skill.name,
                    status_badge,
                    f"{pct:.0f}%",
                    f"{skill.estimated_hours:.0f}h",
                    f"{actual_h:.1f}h",
                    notes_str,
                )
        console.print(table)
        console.print()

        # Run Deviation Detection & Health Snapshot
        detector = DeviationDetector()
        feedbacks = feedback_repo.load_for_roadmap(roadmap.id)
        dev = detector.analyze_deviation(roadmap, records, feedbacks)

        if dev.status == DeviationStatus.ON_TRACK:
            dev_badge = "[bold green]ON TRACK[/bold green]"
            panel_style = "green"
        elif dev.status == DeviationStatus.WARNING:
            dev_badge = "[bold yellow]WARNING[/bold yellow]"
            panel_style = "yellow"
        else:
            dev_badge = "[bold red]CRITICAL DEVIATION[/bold red]"
            panel_style = "red"

        summary_lines = [
            f"• [bold]Schedule Health:[/bold] {dev_badge}",
            f"• [bold]Learning Velocity:[/bold] {dev.velocity_ratio}x (planned pace)",
            f"• [bold]Total Time Logged:[/bold] {dev.total_actual_hours:.1f}h actual / {dev.total_planned_hours:.1f}h planned",
        ]
        if dev.blocked_skills:
            summary_lines.append(f"• [bold red]Blocked Skills:[/bold red] {', '.join(dev.blocked_skills)}")
        if dev.issues:
            for iss in dev.issues:
                summary_lines.append(f"• [yellow]Signal:[/yellow] {iss}")
        if dev.recommendations:
            for recommendation in dev.recommendations:
                summary_lines.append(f"• [cyan]Recommendation:[/cyan] {recommendation}")

        if dev.requires_adaptation:
            summary_lines.append(
                "\n[bold yellow]💡 Recommendation:[/bold yellow] Run [bold]roadmap adapt[/bold] to recalibrate your roadmap."
            )

        console.print(
            Panel(
                "\n".join(summary_lines),
                title="Adaptive Pace & Velocity Analysis",
                border_style=panel_style,
            )
        )
        console.print()


@progress_app.command(name="update")
def update_progress(
    skill: str = typer.Argument(help="Skill name or ID to update"),
    percent: float = typer.Option(..., "--percent", "-p", help="Progress percentage (0-100)"),
    hours: float | None = typer.Option(None, "--hours", "-h", help="Total actual hours spent learning this skill"),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="NOT_STARTED | IN_PROGRESS | BLOCKED | COMPLETED | SKIPPED",
    ),
    notes: str = typer.Option("", "--notes", "-n", help="Optional notes on what was learned or blockers encountered"),
) -> None:
    """Record progress on a specific skill in your active roadmap."""
    initialize_database()

    target_status = None
    if status:
        try:
            target_status = ProgressStatus(status.upper())
        except ValueError as err:
            print_error(f"Invalid status '{status}'. Must be one of: {', '.join([s.value for s in ProgressStatus])}")
            raise typer.Exit(1) from err

    with get_progress_context() as (profile_repo, roadmap_repo, progress_repo, feedback_repo, _):
        profile = profile_repo.load()
        if not profile:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        use_case = UpdateProgressUseCase(
            roadmap_repo=roadmap_repo,
            progress_repo=progress_repo,
            feedback_repo=feedback_repo,
        )

        try:
            res = use_case.execute(
                profile_id=profile.id,
                skill_identifier=skill,
                percentage=percent,
                actual_hours=hours,
                status=target_status,
                notes=notes,
            )
        except ValueError as err:
            print_error(str(err))
            raise typer.Exit(1) from err

        print_success(f"Updated progress for '{res.skill.name}': {res.record.completion_percentage:.0f}% ({res.record.status.value})")
        if res.unlocked_skills:
            console.print(f"  [bold green]🔓 Newly unlocked skills:[/bold green] {', '.join(res.unlocked_skills)}")
        console.print(f"  [bold]Overall Roadmap Progress:[/bold] {res.overall_percentage:.1f}%")

        if res.deviation_report.requires_adaptation:
            console.print(
                "\n  [bold yellow]⚠ Notice:[/bold yellow] Schedule deviation is [bold red]CRITICAL[/bold red]. "
                "Run [bold cyan]roadmap adapt[/bold cyan] to review recommended schedule updates."
            )
        console.print()
