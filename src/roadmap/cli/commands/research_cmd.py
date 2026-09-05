"""
CLI command: roadmap research and roadmap research show.

Executes real-time market intelligence, job requirement sampling, and resource research.
"""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from roadmap.cli.container import get_research_context, initialize_database
from roadmap.cli.display.console import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)

research_app = typer.Typer(help="Research market requirements and learning resources.")


@research_app.callback(invoke_without_command=True)
def default_research(
    ctx: typer.Context,
    market: bool = typer.Option(True, "--market/--no-market", help="Include market intelligence"),
    resources: bool = typer.Option(True, "--resources/--no-resources", help="Include learning resource research"),
    refresh: bool = typer.Option(False, "--refresh", help="Force re-research (bypass cache)"),
) -> None:
    """Execute research on career goals and target skills."""
    if ctx.invoked_subcommand is not None:
        return

    initialize_database()

    with get_research_context() as (profile_repo, source_repo, evidence_repo, run_repo, research_svc):
        profile = profile_repo.load()
        if not profile:
            print_error("No profile found. Run [bold]roadmap init[/bold] first.")
            raise typer.Exit(1)

        topic = profile.target_role or profile.target_goal
        if profile.target_markets:
            target_market = ", ".join(profile.target_markets)
        elif profile.preferred_industry:
            target_market = profile.preferred_industry
        else:
            target_market = "Global / Tech Industry"

        console.print(
            Panel(
                f"[bold cyan]Research Target:[/bold cyan] {topic}\n"
                f"[bold cyan]Target Markets:[/bold cyan] {target_market}\n"
                f"[bold cyan]Market Research:[/bold cyan] {'Enabled' if market else 'Disabled'}\n"
                f"[bold cyan]Resources Research:[/bold cyan] {'Enabled' if resources else 'Disabled'}\n"
                f"[bold cyan]Cache Refresh:[/bold cyan] {'Forced' if refresh else 'Cached if available'}",
                title="[bold green]RoadmapAI Research Pipeline[/bold green]",
                border_style="cyan",
            )
        )

        if research_svc is None:
            print_error(
                "ResearchService could not be initialized. Please configure GEMINI_API_KEY / OPENAI_API_KEY and EXA_API_KEY, "
                "or run with ROADMAP_LLM_PROVIDER=mock and ROADMAP_SEARCH_PROVIDER=mock."
            )
            raise typer.Exit(1)

        def on_progress(step_msg: str) -> None:
            console.print(f"[bold yellow]>[/bold yellow] {step_msg}")

        try:
            run, market_result, resource_result = research_svc.execute_research(
                profile_id=profile.id,
                topic=topic,
                target_market=target_market,
                focus_skills=list(profile.current_skills),
                include_market=market,
                include_resources=resources,
                force_refresh=refresh,
                progress_callback=on_progress,
            )
        except Exception as exc:
            print_error(f"Research pipeline encountered an error: {exc}")
            raise typer.Exit(1) from exc

        console.print()
        if run.status.lower() == "completed":
            print_success(f"Research completed successfully! (Status: {run.status.upper()})")
        elif run.status.lower() == "partial":
            print_warning(
                f"Research partially completed (Status: PARTIAL). "
                f"Analyzed {run.source_count} sources, extracted {run.evidence_count} evidence items."
            )
        else:
            print_error(f"Research failed (Status: {run.status.upper()}).")

        # Display Market Observations
        if market_result.skill_observations:
            table = Table(
                title=f"Sampled Market Skill Requirements (Sample size: {market_result.total_postings_sampled})",
                border_style="cyan",
            )
            table.add_column("Skill", style="bold white")
            table.add_column("Sample Mentions", justify="center")
            table.add_column("Observed Frequency", justify="center", style="green")
            table.add_column("Evidence Grounding", style="dim")

            for obs in market_result.skill_observations[:10]:
                freq_pct = f"{int(obs.observed_frequency * 100)}%"
                ev_count = f"{len(obs.supporting_evidence_ids)} citations"
                table.add_row(
                    obs.skill_name,
                    f"{obs.mentions} / {obs.sample_size}",
                    freq_pct,
                    ev_count,
                )
            console.print(table)
            print_info("[dim]*Note: Observed frequency represents the sampled job postings, not a complete census.[/dim]")

        # Display Recommended Resources
        if resource_result.resources:
            res_table = Table(title="Top Verified Learning Resources", border_style="green")
            res_table.add_column("Title", style="bold white")
            res_table.add_column("Provider / Domain")
            res_table.add_column("Type", justify="center")
            res_table.add_column("Target Skill")

            for r in resource_result.resources[:8]:
                res_table.add_row(
                    r.title[:45],
                    r.provider[:25],
                    r.resource_type.upper(),
                    r.related_skill,
                )
            console.print(res_table)

        console.print(
            f"\n[bold]Total Sources Analyzed:[/bold] {run.source_count}  |  "
            f"[bold]Total Evidence Claims Extracted:[/bold] {run.evidence_count}"
        )
        print_info("Run [bold]roadmap sources[/bold] to inspect underlying URLs and reliability scores.")


@research_app.command(name="show")
def show_research() -> None:
    """Display the latest completed research run."""
    initialize_database()
    with get_research_context() as (profile_repo, source_repo, evidence_repo, run_repo, _):
        profile = profile_repo.load()
        profile_id = profile.id if profile else None
        latest = run_repo.get_latest(profile_id=profile_id)

        if not latest:
            print_warning("No research runs found. Run [bold]roadmap research[/bold] first.")
            raise typer.Exit(0)

        started = latest.started_at.strftime("%Y-%m-%d %H:%M UTC") if latest.started_at else "Unknown"
        queries_fmt = "\n".join(f"  • {q}" for q in latest.queries) if latest.queries else "  None recorded"

        console.print(
            Panel(
                f"[bold cyan]Research Run ID:[/bold cyan] {latest.id}\n"
                f"[bold cyan]Topic:[/bold cyan] {latest.topic}\n"
                f"[bold cyan]Market / Role:[/bold cyan] {latest.target_market or 'General'}\n"
                f"[bold cyan]Started At:[/bold cyan] {started}\n"
                f"[bold cyan]Status:[/bold cyan] [bold green]{latest.status.upper()}[/bold green]\n"
                f"[bold cyan]Unique Sources:[/bold cyan] {latest.source_count}\n"
                f"[bold cyan]Evidence Items:[/bold cyan] {latest.evidence_count}\n\n"
                f"[bold cyan]Queries Executed:[/bold cyan]\n{queries_fmt}",
                title="[bold green]Latest Research Run[/bold green]",
                border_style="cyan",
            )
        )
