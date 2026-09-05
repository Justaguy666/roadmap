"""
Main Typer application — registers all commands.

Command structure:
  roadmap init
  roadmap profile show
  roadmap profile edit
  roadmap profile reset
  roadmap show [--phase N]
  roadmap progress
  roadmap research [--refresh]        (MVP-3 stub)
  roadmap generate                    (MVP-2 stub)
  roadmap complete <skill>            (MVP-5 stub)
  roadmap update                      (MVP-5 stub)
  roadmap why <skill>                 (MVP-5 stub)
  roadmap sources                     (MVP-3 stub)
  roadmap export [--format]           (MVP-6 stub)
"""

from __future__ import annotations

import typer

from roadmap.cli.commands import (
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

# ── Core commands (MVP-1) ─────────────────────────────────────────────────────
app.add_typer(init_cmd.app, name="init", invoke_without_command=True)
app.add_typer(profile_cmd.app, name="profile")
app.add_typer(show_cmd.app, name="show", invoke_without_command=True)
app.add_typer(progress_cmd.app, name="progress", invoke_without_command=True)

# ── Stub commands (MVP-2+) ────────────────────────────────────────────────────
app.add_typer(stub_commands.research_app, name="research", invoke_without_command=True)
app.add_typer(stub_commands.generate_app, name="generate", invoke_without_command=True)
app.add_typer(stub_commands.complete_app, name="complete", invoke_without_command=True)
app.add_typer(stub_commands.update_app, name="update", invoke_without_command=True)
app.add_typer(stub_commands.why_app, name="why", invoke_without_command=True)
app.add_typer(stub_commands.sources_app, name="sources", invoke_without_command=True)
app.add_typer(stub_commands.export_app, name="export", invoke_without_command=True)
