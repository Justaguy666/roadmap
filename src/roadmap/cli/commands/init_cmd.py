"""
CLI command: `roadmap init`

Interactive wizard to create the user profile.
This is the entry point for all new users.
"""

from __future__ import annotations

import typer
from rich.prompt import Confirm, Prompt

from roadmap.application.use_cases.profile_use_cases import CreateProfileRequest
from roadmap.cli.container import get_profile_use_cases, initialize_database
from roadmap.cli.display.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)
from roadmap.cli.display.tables import render_profile_table
from roadmap.domain.exceptions import ProfileNotFoundError
from roadmap.domain.value_objects import BudgetPreference, SkillLevel

app = typer.Typer()


def _prompt_skill_level(prompt: str, default: SkillLevel = SkillLevel.FAMILIAR) -> SkillLevel:
    levels = [lvl.value for lvl in SkillLevel]
    level_str = Prompt.ask(
        prompt,
        choices=levels,
        default=default.value,
    )
    return SkillLevel(level_str)


def _prompt_list(prompt: str, hint: str = "comma-separated") -> list[str]:
    raw = Prompt.ask(f"{prompt} [dim]({hint})[/dim]", default="")
    return [s.strip() for s in raw.split(",") if s.strip()]


def _prompt_budget() -> BudgetPreference:
    choices = [b.value for b in BudgetPreference]
    val = Prompt.ask("Budget preference", choices=choices, default=BudgetPreference.ANY.value)
    return BudgetPreference(val)


@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing profile"),
) -> None:
    """
    Create a new user profile interactively.

    This is the first step — run this before anything else.
    """
    initialize_database()

    console.print()
    console.print("  [bold highlight]RoadmapAI[/bold highlight]")
    console.print("  [dim]Let's build your personalized learning roadmap.[/dim]")
    console.print()

    with get_profile_use_cases() as (create_uc, get_uc, _, __):
        try:
            existing = get_uc.execute()
            if not force:
                print_warning(
                    f"A profile for [bold]{existing.name}[/bold] already exists."
                )
                if not Confirm.ask("  Overwrite it?", default=False):
                    print_info("Run `roadmap profile` to view your current profile.")
                    raise typer.Exit(0)
        except ProfileNotFoundError:
            pass

        # ── Gather inputs ──────────────────────────────────────────────
        print_header("Profile Setup")

        name = Prompt.ask("  Your name")
        target_goal = Prompt.ask(
            "  Goal  [dim](e.g. 'Become a Game Programmer')[/dim]"
        )
        target_role = Prompt.ask(
            "  Target role  [dim](e.g. 'Gameplay Programmer', or press Enter to skip)[/dim]",
            default="",
        )

        console.print()
        console.print("  [bold]Current Level[/bold]")
        console.print(
            "  [dim]missing/familiar/learning/proficient/mastered[/dim]"
        )
        current_level = _prompt_skill_level("  Your overall level", SkillLevel.FAMILIAR)

        console.print()
        current_skills = _prompt_list("  Current skills you already have")
        languages = _prompt_list("  Programming languages you know")
        previous_exp = Prompt.ask("  Previous experience  [dim](brief description)[/dim]", default="")
        completed_projects = _prompt_list("  Completed projects  [dim](notable ones)[/dim]")

        console.print()
        preferred_industry = Prompt.ask(
            "  Preferred industry  [dim](e.g. 'Game Development')[/dim]",
            default="",
        )
        target_markets = _prompt_list("  Target job markets  [dim](e.g. Vietnam, Japan)[/dim]")
        learning_prefs = _prompt_list(
            "  Learning preferences  [dim](video, book, hands-on, course)[/dim]"
        )

        console.print()
        hours_str = Prompt.ask("  Study hours per day", default="2")
        try:
            study_hours = float(hours_str)
        except ValueError:
            study_hours = 2.0

        deadline_str = Prompt.ask("  Deadline in months", default="12")
        try:
            deadline_months = int(deadline_str)
        except ValueError:
            deadline_months = 12

        budget = _prompt_budget()
        constraints = _prompt_list(
            "  Any constraints  [dim](e.g. 'English only', or press Enter to skip)[/dim]"
        )

        # ── Create profile ─────────────────────────────────────────────
        console.print()
        request = CreateProfileRequest(
            name=name,
            target_goal=target_goal,
            target_role=target_role,
            current_level=current_level,
            current_skills=current_skills,
            programming_languages=languages,
            previous_experience=previous_exp,
            completed_projects=completed_projects,
            preferred_industry=preferred_industry,
            target_markets=target_markets,
            learning_preferences=learning_prefs,
            budget=budget,
            constraints=constraints,
            study_hours_per_day=study_hours,
            deadline_months=deadline_months,
        )

        try:
            profile = create_uc.execute(request, overwrite=True)
            print_success(f"Profile created for [bold]{profile.name}[/bold].")
            console.print()
            render_profile_table(profile)
            console.print()
            print_info("Next step: run [bold]roadmap generate[/bold] to create your roadmap.")
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from e
