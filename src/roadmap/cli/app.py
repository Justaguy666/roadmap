"""
Main Typer application — registers all commands.

Command structure:
  roadmap init
  roadmap profile [show|edit|reset]
  roadmap analyze                     (MVP-2 functional)
  roadmap generate [--replace]        (MVP-2 functional)
  roadmap show [--phase N] [--all]
  roadmap progress
  roadmap research [--refresh]        (MVP-3 stub)
  roadmap complete <skill>            (MVP-5 stub)
  roadmap update                      (MVP-5 stub)
  roadmap why <skill>                 (MVP-5 stub)
  roadmap sources                     (MVP-3 stub)
  roadmap export [--format]           (MVP-6 stub)
"""

from __future__ import annotations

import typer

from roadmap.cli.commands import (
    adapt_cmd,
    analyze_cmd,
    evidence_cmd,
    feedback_cmd,
    generate_cmd,
    graph_cmd,
    init_cmd,
    knowledge_cmd,
    profile_cmd,
    progress_cmd,
    quota_cmd,
    research_cmd,
    show_cmd,
    sources_cmd,
    stub_commands,
)

app = typer.Typer(
    name="roadmap",
    help=(
        "RoadmapAI — AI-powered adaptive learning and career roadmap agent.\n\n"
        "Start with: roadmap init"
    ),
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
)

# ── Direct commands ───────────────────────────────────────────────────────────
app.command(name="init", help="Create a new user profile interactively.")(init_cmd.init)
app.command(name="analyze", help="Analyze your career goal to infer target competencies and skills.")(analyze_cmd.analyze)
app.command(name="generate", help="Generate a personalized, validated learning roadmap using AI.")(generate_cmd.generate)
app.command(name="show", help="Display the current roadmap overview or phase curriculum.")(show_cmd.show)
app.command(name="quota", help="Display LLM application request budget and provider health.")(quota_cmd.quota)
app.command(name="why", help="Explain why a skill is included, prioritized, or postponed.")(stub_commands.why)
app.command(name="history", help="Show version history of generated and adapted roadmaps.")(adapt_cmd.history_cmd)
app.command(name="why-change", help="Explain why a roadmap version was adapted from its predecessor.")(adapt_cmd.why_change_cmd)

# ── Command groups & functional subcommands ──────────────────────────────────
app.add_typer(profile_cmd.app, name="profile", help="Manage your user profile (show, edit, reset).")
app.add_typer(progress_cmd.progress_app, name="progress", help="Show learning progress dashboard or update skill status.")
app.add_typer(feedback_cmd.feedback_app, name="feedback", help="Submit qualitative feedback on difficulty, confidence, or blockers.")
app.add_typer(adapt_cmd.adapt_app, name="adapt", help="Analyze progress, detect deviations, and adapt roadmap.")
app.add_typer(research_cmd.research_app, name="research", help="Research market requirements and learning resources.")
app.add_typer(sources_cmd.sources_app, name="sources", help="List all research sources and citations.")
app.add_typer(graph_cmd.graph_app, name="graph", help="Visualize and validate the skill prerequisite dependency DAG.")
app.add_typer(evidence_cmd.evidence_app, name="evidence", help="Inspect aggregated research evidence for a skill.")
app.add_typer(knowledge_cmd.knowledge_app, name="knowledge", help="Knowledge Intelligence, embeddings, and semantic evidence retrieval.")

# ── Backwards-compatibility aliases / stubs ──────────────────────────────────
@app.command(name="complete", help="Mark a skill as 100% complete.")
def complete_skill(
    skill: str = typer.Argument(help="Skill name or ID to complete"),
    hours: float | None = typer.Option(None, "--hours", "-h", help="Total hours spent"),
    notes: str = typer.Option("", "--notes", "-n", help="Notes"),
) -> None:
    """Convenience alias for `roadmap progress update <skill> --percent 100`."""
    progress_cmd.update_progress(skill=skill, percent=100.0, hours=hours, status="COMPLETED", notes=notes)


@app.command(name="update", help="Adaptive replanning alias (same as `roadmap adapt`).")
def update_replan(
    force: bool = typer.Option(False, "--force", "-f", help="Force replanning"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without prompt"),
) -> None:
    """Convenience alias for `roadmap adapt`."""
    adapt_cmd.adapt(force=force, yes=yes)


app.command(name="export", help="Export the roadmap as JSON or Markdown. [MVP-6]")(stub_commands.export)
