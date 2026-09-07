"""CLI command: `roadmap feedback`."""

from __future__ import annotations

import typer

from roadmap.application.use_cases.record_feedback import RecordFeedbackUseCase
from roadmap.cli.container import get_progress_context, initialize_database
from roadmap.cli.display.console import console, print_error, print_success

feedback_app = typer.Typer(help="Record qualitative learning feedback.")


@feedback_app.callback(invoke_without_command=True)
def feedback(
    skill: str | None = typer.Option(None, "--skill", "-s", help="Skill name or ID to provide feedback on"),
    difficulty: int = typer.Option(3, "--difficulty", "-d", help="Difficulty rating 1 (Very Easy) to 5 (Extremely Hard)"),
    confidence: int = typer.Option(3, "--confidence", "-c", help="Confidence level 1 (Lost) to 5 (Mastered)"),
    satisfaction: int = typer.Option(3, "--satisfaction", help="Satisfaction rating 1 (Frustrated) to 5 (Delighted)"),
    blocked: str = typer.Option("", "--blocked", "-b", help="Specific blocker or issue encountered"),
    notes: str = typer.Option("", "--notes", "-n", help="Open-ended reflections or observations"),
) -> None:
    """Submit qualitative feedback on pacing, difficulty, or blockers."""
    initialize_database()

    with get_progress_context() as (profile_repo, roadmap_repo, _, feedback_repo, _):
        profile = profile_repo.load()
        if not profile:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        use_case = RecordFeedbackUseCase(
            roadmap_repo=roadmap_repo,
            feedback_repo=feedback_repo,
        )

        try:
            fb = use_case.execute(
                profile_id=profile.id,
                difficulty=difficulty,
                confidence=confidence,
                satisfaction=satisfaction,
                skill_identifier=skill,
                blocked_reason=blocked,
                free_text=notes,
            )
        except ValueError as err:
            print_error(str(err))
            raise typer.Exit(1) from err

        print_success("Feedback saved successfully!")
        target = f"for skill '[bold]{fb.skill_name}[/bold]'" if fb.skill_name else "for current roadmap"
        console.print(f"  Target: {target}")
        console.print(f"  Difficulty: {fb.difficulty}/5 | Confidence: {fb.confidence}/5 | Satisfaction: {fb.satisfaction}/5")
        if fb.blocked_reason:
            console.print(f"  [bold red]Blocker:[/bold red] {fb.blocked_reason}")
        if fb.free_text:
            console.print(f"  [dim]Notes:[/dim] {fb.free_text}")
        console.print()
