"""
CLI command: `roadmap generate [--replace]`

Constructs an end-to-end learning roadmap with goal analysis,
deterministic skill gap calculation, and LLM planning.
"""

from __future__ import annotations

import typer
from rich.prompt import Confirm

from roadmap.application.ports.llm_provider import LLMProviderError, MissingAPIKeyError
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
            console.print("  [bold]Analyzing goal...[/bold]")
            with spin("Inferring core competencies and required skills..."):
                goal_analysis = analyze_uc.execute(profile)
            print_success(f"Goal analyzed: resolved role as [bold]{goal_analysis.target_role}[/bold].")

            console.print()
            console.print("  [bold]Calculating skill gaps...[/bold]")
            skill_gaps = generate_uc._compute_skill_gaps(profile, goal_analysis)
            print_success(
                f"Gaps calculated: {skill_gaps.total_gaps} actionable skill gaps identified "
                f"({skill_gaps.critical_gaps_count} critical)."
            )

            console.print()
            console.print("  [bold]Generating roadmap...[/bold]")
            with spin("Synthesizing phases, projects, and milestone criteria..."):
                draft_result, roadmap, val_result = generate_uc._generate_and_validate(
                    profile=profile,
                    goal_analysis=goal_analysis,
                    skill_gaps=skill_gaps,
                )
            print_success("Roadmap drafted.")

            console.print()
            console.print("  [bold]Validating roadmap...[/bold]")
            if not val_result.is_valid:
                errors = [e.message for e in val_result.errors]
                print_error(f"Roadmap failed deterministic validation: {'; '.join(errors)}")
                raise RoadmapValidationError(errors)
            print_success("Validation passed (zero structural defects).")

            console.print()
            console.print("  [bold]Saving roadmap...[/bold]")
            roadmap_repo.save(roadmap)
            print_success("Roadmap saved.")

            console.print()
            print_header(f"✓ Roadmap generated successfully: {roadmap.title}")
            console.print(
                f"  Phases: [bold]{len(roadmap.phases)}[/bold]  |  "
                f"Skills: [bold]{len(roadmap.all_skills)}[/bold]  |  "
                f"Estimated Duration: [bold]{roadmap.total_weeks} weeks[/bold] (~{roadmap.total_estimated_hours:.0f} hours)"
            )
            console.print()
            print_info("Run [bold]roadmap show[/bold] to explore your complete curriculum.")
            console.print()

    except MissingAPIKeyError as e:
        print_error(str(e))
        print_info("Set your key in .env or run with a mock provider: ROADMAP_LLM_PROVIDER=fake")
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
