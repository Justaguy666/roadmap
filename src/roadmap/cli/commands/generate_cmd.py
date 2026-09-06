"""
CLI command: `roadmap generate [--replace]`

Constructs an end-to-end learning roadmap with goal analysis,
deterministic skill gap calculation, and LLM planning.
"""

from __future__ import annotations

import typer
from rich.prompt import Confirm

from roadmap.application.ports.llm_provider import (
    ApplicationBudgetExceededError,
    LLMProviderError,
    MissingAPIKeyError,
    ProviderQuotaUnavailableError,
)
from roadmap.cli.container import get_generator_context, initialize_database
from roadmap.cli.display.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    spin,
)
from roadmap.domain.exceptions import RoadmapValidationError

app = typer.Typer()


@app.command()
def generate(
    replace: bool = typer.Option(
        False,
        "--replace",
        "-r",
        help="Overwrite existing roadmap without prompting for confirmation",
    ),
) -> None:
    """Generate a personalized, validated learning roadmap using AI."""
    initialize_database()

    try:
        with get_generator_context() as (profile_repo, roadmap_repo, generate_uc, analyze_uc):
            console.print()
            console.print("  [bold]Loading profile...[/bold]")
            profile = profile_repo.load()
            if profile is None:
                print_error("No profile found. Run `roadmap init` first.")
                raise typer.Exit(1)
            print_success("Profile loaded.")

            # Check if roadmap already exists
            existing_roadmap = roadmap_repo.load_latest(profile.id)
            if existing_roadmap is not None and not replace:
                console.print()
                print_warning(
                    f"A roadmap titled '[bold]{existing_roadmap.title}[/bold]' already exists."
                )
                if not Confirm.ask("  Do you want to replace it?", default=False):
                    print_info("Roadmap generation cancelled. Existing roadmap preserved.")
                    raise typer.Exit(0)

            console.print()
            console.print("  [bold]Generating evidence-backed roadmap...[/bold]")
            with spin("Synthesizing market research, dependency graph, and curriculum..."):
                roadmap, goal_analysis, skill_gaps, val_result = generate_uc.execute(
                    profile=profile,
                    existing_goal_analysis=None,
                    progress_callback=lambda msg: console.print(f"    [dim]• {msg}[/dim]"),
                )
            print_success(f"Roadmap generated (v{roadmap.version}) with quality score {roadmap.quality_score:.1f}/100.")

            console.print()
            print_header(f"✓ Roadmap generated successfully: {roadmap.title} (v{roadmap.version})")
            console.print(
                f"  Phases: [bold]{len(roadmap.phases)}[/bold]  |  "
                f"Skills: [bold]{len(roadmap.all_skills)}[/bold]  |  "
                f"Quality: [bold cyan]{roadmap.quality_score:.1f}/100[/bold cyan]  |  "
                f"Estimated Duration: [bold]{roadmap.total_weeks} weeks[/bold] (~{roadmap.total_estimated_hours:.0f} hours)"
            )
            console.print()
            print_info("Run [bold]roadmap show[/bold] to explore your complete curriculum.")
            print_info("Run [bold]roadmap graph[/bold] to inspect the skill dependency DAG.")
            print_info("Run [bold]roadmap why <skill>[/bold] to inspect decision rationale.")
            console.print()

    except MissingAPIKeyError as e:
        print_error(str(e))
        print_info("Set your key in .env or run with a mock provider: ROADMAP_LLM_PROVIDER=mock")
        raise typer.Exit(1) from e
    except ApplicationBudgetExceededError as e:
        console.print()
        print_error(f"LLM application budget exhausted: {e}")
        console.print()
        console.print("  [bold]Workflow:[/bold] generation")
        console.print(f"  [bold]Allocated limit:[/bold] {e.allocated}")
        console.print(f"  [bold]Used in window:[/bold] {e.used}")
        console.print(f"  [bold]Required:[/bold] {e.required}")
        console.print()
        console.print("  [bold yellow]Suggested next actions:[/bold yellow]")
        console.print("  • Wait for the configured budget window to reset (check with `roadmap quota`)")
        console.print("  • Run with mock/offline mode: [dim]ROADMAP_LLM_PROVIDER=mock ROADMAP_SEARCH_PROVIDER=mock[/dim]")
        console.print("  • Increase application budget configuration (e.g. [dim]ROADMAP_GENERATION_LLM_BUDGET[/dim] in .env)")
        console.print("  • Change provider or model (e.g. switch between Gemini and OpenAI)")
        console.print()
        raise typer.Exit(1) from e
    except ProviderQuotaUnavailableError as e:
        console.print()
        print_error(f"Provider quota unavailable: {e}")
        console.print()
        console.print(f"  [bold]Provider:[/bold] {e.provider}")
        console.print(f"  [bold]Model:[/bold] {e.model}")
        console.print()
        console.print("  [bold yellow]Suggested next actions:[/bold yellow]")
        console.print("  • The provider daily quota has been exhausted; requests are cooling down to avoid wasted calls.")
        console.print("  • Run `roadmap quota` to inspect provider status.")
        console.print("  • Switch provider (e.g. [dim]ROADMAP_LLM_PROVIDER=openai[/dim]) or use offline mode ([dim]ROADMAP_LLM_PROVIDER=mock[/dim]).")
        console.print()
        raise typer.Exit(1) from e
    except LLMProviderError as e:
        print_error(f"LLM Provider Error: {e}")
        raise typer.Exit(1) from e
    except RoadmapValidationError as e:
        print_error(f"Validation Error: {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        raise typer.Exit(1) from e
