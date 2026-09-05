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
    analyze_cmd,
    generate_cmd,
    init_cmd,
    profile_cmd,
    progress_cmd,
    show_cmd,
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
app.command(name="progress", help="Show overall learning progress across all phases.")(progress_cmd.progress)

# ── Command groups ────────────────────────────────────────────────────────────
app.add_typer(profile_cmd.app, name="profile", help="Manage your user profile (show, edit, reset).")

# ── Stub commands (MVP-3+) ────────────────────────────────────────────────────
app.command(name="research", help="Research market requirements and learning resources. [MVP-3]")(stub_commands.research)
app.command(name="complete", help="Mark a skill as complete. [MVP-5]")(stub_commands.complete)
app.command(name="update", help="Replan roadmap based on current progress. [MVP-5]")(stub_commands.update)
app.command(name="why", help="Explain why a skill is included or postponed. [MVP-5]")(stub_commands.why)
app.command(name="sources", help="List all research sources. [MVP-3]")(stub_commands.sources)
app.command(name="export", help="Export the roadmap as JSON or Markdown. [MVP-6]")(stub_commands.export)
