"""Rich panel renderers for explanations and structured output."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from roadmap.cli.display.console import console
from roadmap.domain.entities.source import Recommendation


def render_why_panel(
    skill_name: str,
    recommendation: Recommendation,
    evidence_claims: list[str],
    source_info: list[str],
) -> None:
    """
    Render the `roadmap why <skill>` explanation panel.
    """
    lines: list[str] = []

    # Evidence section
    if evidence_claims or source_info:
        lines.append("[bold]Evidence[/bold]")
        lines.append("─" * 40)
        for claim in evidence_claims[:5]:
            lines.append(f"  · {claim}")
        if source_info:
            lines.append(f"  [dim]{', '.join(source_info[:3])}[/dim]")
        lines.append("")

    # Reasoning section
    lines.append("[bold]Reasoning[/bold]")
    lines.append("─" * 40)
    lines.append(f"  {recommendation.reasoning}")
    lines.append("")

    # Decision section
    lines.append("[bold]Decision[/bold]")
    lines.append("─" * 40)
    decision_color = {
        "include": "green",
        "postpone": "yellow",
        "exclude": "red",
    }.get(recommendation.decision, "white")
    lines.append(f"  Decision: [{decision_color}]{recommendation.decision.title()}[/{decision_color}]")
    for factor in recommendation.decision_factors:
        lines.append(f"  · {factor}")
    lines.append("")
    lines.append(f"  [dim]Confidence: {recommendation.confidence:.0%}[/dim]")

    body = "\n".join(lines)
    console.print(Panel(
        body,
        title=f"Why {skill_name}?",
        border_style="dim",
        expand=False,
        padding=(1, 2),
    ))


def render_error_panel(title: str, message: str) -> None:
    console.print(Panel(
        f"  {message}",
        title=f"[error]{title}[/error]",
        border_style="red",
        expand=False,
    ))


def render_success_panel(title: str, message: str) -> None:
    console.print(Panel(
        f"  {message}",
        title=f"[success]{title}[/success]",
        border_style="green",
        expand=False,
    ))
