"""CLI commands: `roadmap adapt`, `roadmap history`, and `roadmap why-change`."""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from roadmap.cli.container import get_adaptation_context, get_progress_context, initialize_database
from roadmap.cli.display.console import console, print_error, print_header, print_info, print_success, print_warning

adapt_app = typer.Typer(help="Adaptive roadmap replanning commands.")


@adapt_app.callback(invoke_without_command=True)
def adapt(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Bypass anti-oscillation checks and force an adaptive replan",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically confirm and apply the adapted roadmap",
    ),
) -> None:
    """Analyze progress and feedback, propose minimal roadmap adaptations, and prompt to apply."""
    initialize_database()

    with get_adaptation_context() as (profile_repo, roadmap_repo, adapt_uc):
        profile = profile_repo.load()
        if not profile:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        roadmap = roadmap_repo.load_latest(profile.id)
        if not roadmap:
            print_error("No roadmap found. Run `roadmap generate` first.")
            raise typer.Exit(1)

        print_header(f"Adaptive Replanning Analysis — {roadmap.title} (v{roadmap.version})")

        with console.status("[bold cyan]Analyzing velocity, deviation signals, and proposing adaptations...[/bold cyan]"):
            try:
                candidate_result = adapt_uc.prepare_adaptation(profile.id, force=force)
            except Exception as err:
                print_error(f"Failed to generate adaptation proposal: {err}")
                raise typer.Exit(1) from err

        dev = candidate_result.deviation_report
        proposal = candidate_result.proposal

        # Deviation Status Summary
        console.print(
            Panel(
                f"• [bold]Deviation Status:[/bold] {dev.status.value}\n"
                f"• [bold]Learning Velocity:[/bold] {dev.velocity_ratio}x\n"
                f"• [bold]Logged vs Planned Hours:[/bold] {dev.total_actual_hours:.1f}h actual / {dev.total_planned_hours:.1f}h planned\n"
                f"• [bold]Blocked Skills:[/bold] {', '.join(dev.blocked_skills) if dev.blocked_skills else 'None'}",
                title="Input Deviation Signals",
                border_style="cyan",
            )
        )
        console.print()

        if candidate_result.blocked_by_anti_oscillation:
            print_warning(candidate_result.anti_oscillation_reason)
            console.print("Use [bold]--force[/bold] if you want to bypass anti-oscillation rate limiting.")
            raise typer.Exit(0)

        if not candidate_result.requires_adaptation and not force:
            print_success("Roadmap is currently well-calibrated! No adaptation required.")
            console.print(f"  [dim]{proposal.rationale}[/dim]")
            raise typer.Exit(0)

        # Show Proposed Adaptation Summary Diff
        console.print(
            Panel(
                f"[bold white]Strategy:[/bold white] [bold yellow]{proposal.adaptation_strategy}[/bold yellow]\n\n"
                f"[bold white]Rationale:[/bold white] {proposal.rationale}\n\n"
                f"[bold white]Confidence:[/bold white] {int(proposal.confidence * 100)}%\n"
                f"[bold white]Total Timeline Delta:[/bold white] {proposal.estimated_total_weeks_delta:+.1f} weeks",
                title=f"Proposed Adaptation (Target: v{roadmap.version + 1})",
                border_style="yellow",
            )
        )
        console.print()

        # Render Changes Table
        if proposal.phase_adjustments or proposal.skill_adjustments or proposal.support_skills:
            diff_table = Table(title="Proposed Modifications", border_style="yellow")
            diff_table.add_column("Type", style="bold white")
            diff_table.add_column("Target")
            diff_table.add_column("Adjustment")
            diff_table.add_column("Rationale", style="dim")

            for p in proposal.phase_adjustments:
                diff_table.add_row("Phase Duration", f"Phase {p.phase_number}", f"{p.new_estimated_weeks:.0f} weeks", p.rationale)

            for s in proposal.skill_adjustments:
                adj_desc = f"{s.action}: {s.new_estimated_hours:.0f}h" if s.new_estimated_hours else s.action
                diff_table.add_row("Skill Pacing", s.skill_name, adj_desc, s.rationale)

            for sup in proposal.support_skills:
                diff_table.add_row("New Support Skill", sup.name, f"+{sup.estimated_hours:.0f}h (Phase {sup.target_phase_number})", sup.rationale)

            console.print(diff_table)
            console.print()

        # Confirmation Gate
        if not yes:
            confirmed = typer.confirm(f"Apply this adaptation and persist roadmap v{roadmap.version + 1}?", default=True)
            if not confirmed:
                print_info("Adaptation cancelled by user. Roadmap remains at current version.")
                raise typer.Exit(0)

        # Apply and persist
        adapted_rm = adapt_uc.apply_adaptation(candidate_result)
        print_success(f"Successfully adapted roadmap to version {adapted_rm.version}!")
        console.print(
            f"  New duration: [bold]{adapted_rm.total_weeks} weeks[/bold] (~{adapted_rm.total_estimated_hours:.0f} hours)\n"
            f"  Run [bold]roadmap show[/bold] or [bold]roadmap progress[/bold] to inspect your updated curriculum.\n"
            f"  Run [bold]roadmap why-change {adapted_rm.version}[/bold] to inspect the adaptation rationale."
        )
        console.print()


def history_cmd() -> None:
    """List historical versions of your roadmap."""
    initialize_database()

    with get_progress_context() as (profile_repo, roadmap_repo, _, _, adaptation_repo):
        profile = profile_repo.load()
        if not profile:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        roadmaps = roadmap_repo.load_all(profile.id)
        if not roadmaps:
            print_info("No roadmaps found.")
            raise typer.Exit(0)

        adaptations = {a.new_version: a for a in adaptation_repo.load_for_profile(profile.id)}

        print_header("Roadmap Version History")

        table = Table(border_style="dim")
        table.add_column("Version", justify="center", style="bold white")
        table.add_column("Created At", style="dim")
        table.add_column("Weeks", justify="center")
        table.add_column("Hours", justify="center")
        table.add_column("Quality Score", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Adaptation Trigger")

        for rm in reversed(roadmaps):
            adapt_rec = adaptations.get(rm.version)
            trigger_text = adapt_rec.trigger_reason if adapt_rec else ("Initial Generation" if rm.version == 1 else "Regeneration")
            created_str = rm.generated_at.strftime("%Y-%m-%d %H:%M")
            is_latest = (rm.id == roadmaps[0].id)
            v_badge = f"[bold green]v{rm.version} (Active)[/bold green]" if is_latest else f"v{rm.version}"

            table.add_row(
                v_badge,
                created_str,
                f"{rm.total_weeks}w",
                f"{rm.total_estimated_hours:.0f}h",
                f"{rm.quality_score:.1f}/100",
                rm.validation_status,
                trigger_text,
            )

        console.print(table)
        console.print()


def why_change_cmd(
    version: int | None = typer.Argument(None, help="Version number to inspect (defaults to latest)"),
) -> None:
    """Explain why a roadmap version was adapted from its predecessor."""
    initialize_database()

    with get_progress_context() as (profile_repo, roadmap_repo, _, _, adaptation_repo):
        profile = profile_repo.load()
        if not profile:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        roadmap = roadmap_repo.load_latest(profile.id)
        if not roadmap:
            print_error("No active roadmap found.")
            raise typer.Exit(1)

        target_version = version if version is not None else roadmap.version
        record = adaptation_repo.load_by_version(profile.id, target_version)

        if not record:
            if target_version == 1:
                print_info("Version 1 is the baseline generated roadmap; it has no prior adaptation history.")
            else:
                print_warning(f"No adaptation audit record found for version {target_version}.")
            raise typer.Exit(0)

        print_header(f"Adaptation Rationale — Version {record.previous_version} ➔ Version {record.new_version}")

        console.print(
            Panel(
                f"[bold white]Trigger Reason:[/bold white] [bold cyan]{record.trigger_reason}[/bold cyan]\n"
                f"[bold white]Timestamp:[/bold white] {record.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"[bold white]Accepted by User:[/bold white] {'Yes' if record.accepted else 'No'}",
                title="Adaptation Overview",
                border_style="cyan",
            )
        )
        console.print()

        # Deviation summary
        dev = record.deviation_summary
        if dev:
            console.print("  [bold]Deviation Context:[/bold]")
            console.print(f"    • Status: [bold red]{dev.get('status', 'N/A')}[/bold red]")
            console.print(f"    • Velocity: {dev.get('velocity_ratio', 'N/A')}x")
            if dev.get("blocked_skills"):
                console.print(f"    • Blocked Skills: {', '.join(dev.get('blocked_skills', []))}")
            console.print()

        # Changes summary
        ch = record.changes_summary
        if ch:
            console.print("  [bold]Applied Adjustments:[/bold]")
            if ch.get("weeks_delta"):
                console.print(f"    • Total Timeline Delta: {ch.get('weeks_delta'):+.1f} weeks")
            if ch.get("phase_adjustments"):
                for p in ch["phase_adjustments"]:
                    console.print(f"    • Phase {p.get('phase_number')}: {p.get('new_estimated_weeks')} weeks — {p.get('rationale')}")
            if ch.get("skill_adjustments"):
                for s in ch["skill_adjustments"]:
                    console.print(f"    • Skill '{s.get('skill_name')}': {s.get('action')} ({s.get('new_estimated_hours')}h) — {s.get('rationale')}")
            if ch.get("support_skills"):
                for sup in ch["support_skills"]:
                    console.print(f"    • Added Support Skill: '{sup.get('name')}' (+{sup.get('estimated_hours')}h) — {sup.get('rationale')}")
            console.print()
