"""
CLI command: `roadmap profile [show|edit|reset]`
"""

from __future__ import annotations

import typer
from rich.prompt import Confirm, Prompt

from roadmap.application.use_cases.profile_use_cases import UpdateProfileRequest
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


@app.command("show")
def profile_show() -> None:
    """Display the current user profile."""
    initialize_database()
    with get_profile_use_cases() as (_, get_uc, __):
        try:
            profile = get_uc.execute()
            print_header(f"Profile — {profile.name}")
            render_profile_table(profile)
            console.print()
        except ProfileNotFoundError as e:
            print_error(str(e))
            raise typer.Exit(1) from e


@app.command("edit")
def profile_edit() -> None:
    """Interactively edit the current profile."""
    initialize_database()
    with get_profile_use_cases() as (_, get_uc, update_uc):
        try:
            profile = get_uc.execute()
        except ProfileNotFoundError as e:
            print_error(str(e))
            raise typer.Exit(1) from e

        print_header(f"Edit Profile — {profile.name}")
        print_info("Press Enter to keep the current value.")
        console.print()

        def ask(label: str, current: str, prompt_text: str) -> str | None:
            console.print(f"  [dim]{label}:[/dim] [bold]{current or '—'}[/bold]")
            new_val = Prompt.ask(f"  New {label}", default="")
            return new_val if new_val.strip() else None

        def ask_list(label: str, current: list[str]) -> list[str] | None:
            current_str = ", ".join(current) if current else "—"
            console.print(f"  [dim]{label}:[/dim] [bold]{current_str}[/bold]")
            raw = Prompt.ask(f"  New {label} (comma-separated)", default="")
            if not raw.strip():
                return None
            return [s.strip() for s in raw.split(",") if s.strip()]

        # Collect changes
        request = UpdateProfileRequest()

        name_new = ask("Name", profile.name, "name")
        if name_new:
            request.name = name_new

        goal_new = ask("Goal", profile.target_goal, "goal")
        if goal_new:
            request.target_goal = goal_new

        role_new = ask("Target role", profile.target_role, "role")
        if role_new:
            request.target_role = role_new

        # Skill level
        levels = [l.value for l in SkillLevel]
        console.print(f"  [dim]Current level:[/dim] [bold]{profile.current_level.value}[/bold]")
        level_new = Prompt.ask(
            "  New level", choices=[""] + levels, default=""
        )
        if level_new:
            request.current_level = SkillLevel(level_new)

        skills_new = ask_list("Current skills", profile.current_skills)
        if skills_new is not None:
            request.current_skills = skills_new

        langs_new = ask_list("Languages", profile.programming_languages)
        if langs_new is not None:
            request.programming_languages = langs_new

        markets_new = ask_list("Target markets", profile.target_markets)
        if markets_new is not None:
            request.target_markets = markets_new

        hours_str = ask("Study hours/day", str(profile.study_hours_per_day), "hours")
        if hours_str:
            try:
                request.study_hours_per_day = float(hours_str)
            except ValueError:
                print_warning("Invalid number, keeping existing value.")

        deadline_str = ask("Deadline months", str(profile.deadline_months), "deadline")
        if deadline_str:
            try:
                request.deadline_months = int(deadline_str)
            except ValueError:
                print_warning("Invalid number, keeping existing value.")

        # Confirm
        console.print()
        if not Confirm.ask("  Save changes?", default=True):
            print_info("No changes saved.")
            raise typer.Exit(0)

        profile = update_uc.execute(request)
        console.print()
        print_success("Profile updated.")
        console.print()
        render_profile_table(profile)
        console.print()


@app.command("reset")
def profile_reset() -> None:
    """Delete the current profile (WARNING: irreversible)."""
    initialize_database()
    with get_profile_use_cases() as (_, get_uc, __):
        try:
            profile = get_uc.execute()
        except ProfileNotFoundError as e:
            print_warning("No profile found.")
            raise typer.Exit(0) from e

        print_warning(f"This will permanently delete the profile for [bold]{profile.name}[/bold].")
        if not Confirm.ask("  Are you sure?", default=False):
            print_info("Cancelled.")
            raise typer.Exit(0)

        get_uc._repo.delete()
        print_success("Profile deleted.")
