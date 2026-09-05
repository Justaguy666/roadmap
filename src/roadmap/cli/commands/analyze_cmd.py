"""
CLI command: `roadmap analyze`

Performs AI Goal Analysis to infer competencies, required skills, and key assumptions.
"""

from __future__ import annotations

import typer
from rich.table import Table

from roadmap.application.ports.llm_provider import LLMProviderError, MissingAPIKeyError
from roadmap.cli.container import get_generator_context, initialize_database
from roadmap.cli.display.console import (
    console,
    print_error,
    print_info,
    spin,
)

app = typer.Typer()


@app.command()
def analyze() -> None:
    """Analyze your career goal to infer target competencies and skills."""
    initialize_database()

    try:
        with get_generator_context() as (profile_repo, _, __, analyze_uc):
            profile = profile_repo.load()
            if profile is None:
                print_error("No profile found. Run `roadmap init` first.")
                raise typer.Exit(1)

            console.print()
            console.print("  [dim]AI Goal Analysis (Conceptual Model — not live market research)[/dim]")
            console.print()

            with spin(f"Analyzing goal for '{profile.name}'..."):
                analysis = analyze_uc.execute(profile)

            # Render Goal Analysis Output
            console.print("  [bold highlight]GOAL ANALYSIS[/bold highlight]")
            console.print("  [dim]══════════════════════════════════════════════════[/dim]")
            console.print()
            console.print("  [bold]Target Role:[/bold]")
            console.print(f"  {analysis.target_role}")
            console.print()
            console.print("  [bold]Interpreted Goal:[/bold]")
            console.print(f"  {analysis.interpreted_goal}")
            console.print()

            # Competencies Table
            console.print("  [bold]Competency Breakdown:[/bold]")
            comp_table = Table(
                show_header=True,
                header_style="bold",
                border_style="dim",
                padding=(0, 1),
            )
            comp_table.add_column("Competency Domain", min_width=24)
            comp_table.add_column("Category", width=14)
            comp_table.add_column("Importance", justify="right", width=12)

            for comp in analysis.competencies:
                comp_table.add_row(
                    comp.name,
                    comp.category.title(),
                    f"{comp.importance_score:.0%}",
                )
            console.print(comp_table)
            console.print()

            # Required Skills Table
            console.print("  [bold]Required Core Skills:[/bold]")
            skill_table = Table(
                show_header=True,
                header_style="bold",
                border_style="dim",
                padding=(0, 1),
            )
            skill_table.add_column("Skill", min_width=24)
            skill_table.add_column("Target Level", width=14)
            skill_table.add_column("Priority", width=10)

            for skill in analysis.required_skills:
                p_style = "critical" if skill.priority.value == "critical" else (
                    "high" if skill.priority.value == "high" else "medium"
                )
                skill_table.add_row(
                    skill.name,
                    skill.target_level.label,
                    f"[{p_style}]{skill.priority.value.upper()}[/{p_style}]",
                )
            console.print(skill_table)
            console.print()

            if analysis.optional_skills:
                console.print("  [bold]Optional / Differentiating Skills:[/bold]")
                for opt in analysis.optional_skills:
                    console.print(f"  [dim]·[/dim] {opt.name} [dim]({opt.category})[/dim]")
                console.print()

            if analysis.assumptions:
                console.print("  [bold]Assumptions:[/bold]")
                for assumption in analysis.assumptions:
                    console.print(f"  [dim]-[/dim] {assumption}")
                console.print()

            console.print(f"  [bold]Confidence:[/bold] [highlight]{analysis.confidence:.2f}[/highlight]")
            console.print()
            console.print("  [dim]Next: run [bold]roadmap generate[/bold] to construct your personalized schedule.[/dim]")
            console.print()

    except MissingAPIKeyError as e:
        print_error(str(e))
        print_info("Set your key in .env or run with a mock provider: ROADMAP_LLM_PROVIDER=fake")
        raise typer.Exit(1) from e
    except LLMProviderError as e:
        print_error(f"LLM Provider Error: {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        raise typer.Exit(1) from e
