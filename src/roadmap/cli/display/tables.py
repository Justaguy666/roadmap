"""Rich table renderers for the roadmap CLI."""

from __future__ import annotations

from rich.table import Table

from roadmap.cli.display.console import console
from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects import Priority, SkillStatus


def _phase_status(phase: RoadmapPhase, progress_map: dict[str, float]) -> str:
    """Return a Rich-formatted status string for a phase."""
    pct = phase.completion_percentage
    # Override with progress_map if provided
    if phase.skills and progress_map:
        total = sum(progress_map.get(s.id, 0.0) for s in phase.skills)
        pct = total / len(phase.skills)
    if pct >= 100 or phase.is_completed:
        return "[phase_done]✓ Done[/phase_done]"
    if pct > 0:
        return f"[phase_active]{pct:.0f}%[/phase_active]"
    return "[phase_pending]  0%[/phase_pending]"


def render_roadmap_overview(
    roadmap: Roadmap,
    progress_map: dict[str, float] | None = None,
) -> None:
    """Render a high-level phase overview table."""
    if progress_map is None:
        progress_map = {}

    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        show_lines=False,
        padding=(0, 1),
        expand=False,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Phase", min_width=30)
    table.add_column("Skills", justify="right", width=7)
    table.add_column("Weeks", justify="right", width=7)
    table.add_column("Status", justify="right", width=12)

    for phase in roadmap.phases:
        status = _phase_status(phase, progress_map)
        table.add_row(
            str(phase.phase_number),
            phase.name,
            str(len(phase.skills)),
            f"{phase.estimated_weeks:.0f}w",
            status,
        )

    console.print(table)

    # Summary line
    overall = roadmap.overall_completion_percentage
    console.print()
    console.print(
        f"  [dim]Total: ~{roadmap.total_estimated_hours:.0f}h over "
        f"{roadmap.total_weeks} weeks   "
        f"Overall: {overall:.0f}%[/dim]"
    )


def render_phase_detail(phase: RoadmapPhase) -> None:
    """Render detailed skills and resources for a single phase."""
    table = Table(
        show_header=True,
        header_style="bold",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Skill", min_width=25)
    table.add_column("Level", width=12)
    table.add_column("→ Target", width=12)
    table.add_column("Hours", justify="right", width=7)
    table.add_column("Priority", width=10)
    table.add_column("Status", width=12)

    for skill in phase.skills:
        priority_style = {
            Priority.CRITICAL: "critical",
            Priority.HIGH: "high",
            Priority.MEDIUM: "medium",
            Priority.LOW: "low",
        }.get(skill.priority, "dim")

        status_str = {
            SkillStatus.COMPLETED: "[skill_done]✓ Done[/skill_done]",
            SkillStatus.IN_PROGRESS: "[skill_progress]In Progress[/skill_progress]",
            SkillStatus.PENDING: "[skill_pending]Pending[/skill_pending]",
            SkillStatus.POSTPONED: "[dim]Postponed[/dim]",
            SkillStatus.SKIPPED: "[dim]Skipped[/dim]",
        }.get(skill.status, "")

        table.add_row(
            skill.name,
            skill.current_level.label,
            skill.target_level.label,
            f"{skill.estimated_hours:.0f}h" if skill.estimated_hours else "—",
            f"[{priority_style}]{skill.priority.value.title()}[/{priority_style}]",
            status_str,
        )

    console.print(table)

    if phase.resources:
        console.print()
        console.print("  [bold]Resources[/bold]")
        for r in phase.resources:
            cost_str = "Free" if r.is_free else f"${r.cost:.0f}"
            console.print(
                f"    [dim]·[/dim] {r.title}  "
                f"[dim]{r.provider}  {cost_str}  ~{r.estimated_hours:.0f}h[/dim]"
            )

    if phase.projects:
        console.print()
        console.print("  [bold highlight]Projects[/bold highlight]")
        for p in phase.projects:
            console.print(f"    [bold]{p.name}[/bold] [dim](~{p.estimated_hours:.0f}h, difficulty: {p.difficulty.label})[/dim]")
            if p.description:
                console.print(f"      [dim]{p.description}[/dim]")
            if p.expected_outcome:
                console.print(f"      [info]Deliverable:[/info] {p.expected_outcome}")

    if phase.milestones:
        console.print()
        console.print("  [bold highlight]Milestones & Exit Criteria[/bold highlight]")
        for m in phase.milestones:
            m_status = "[phase_done]✓ Achieved[/phase_done]" if m.is_achieved else "[phase_pending]Pending[/phase_pending]"
            console.print(f"    [bold]{m.name}[/bold] — {m_status}")
            if m.exit_criteria:
                for crit in m.exit_criteria:
                    console.print(f"      [dim][ ][/dim] {crit}")

    if phase.resources:
        console.print()
        console.print("  [bold highlight]Curated Learning Resources[/bold highlight]")
        for r in phase.resources:
            cost_str = "Free" if r.is_free else f"${r.cost:.0f}"
            console.print(
                f"    [dim]·[/dim] {r.title}  "
                f"[dim]{r.provider}  {cost_str}  ~{r.estimated_hours:.0f}h[/dim]"
            )


def render_profile_table(profile: UserProfile) -> None:
    """Render a formatted profile summary."""
    table = Table(
        show_header=False,
        border_style="dim",
        padding=(0, 2),
        expand=False,
    )
    table.add_column("Field", style="bold dim", width=22)
    table.add_column("Value")

    def row(label: str, value: str) -> None:
        table.add_row(label, value or "[dim]—[/dim]")

    row("Name", profile.name)
    row("Goal", profile.target_goal)
    row("Target Role", profile.target_role)
    row("Current Level", profile.current_level.label)
    row("Current Skills", ", ".join(profile.current_skills) or "—")
    row("Languages", ", ".join(profile.programming_languages) or "—")
    row("Industry", profile.preferred_industry)
    row("Target Markets", ", ".join(profile.target_markets) or "—")
    row("Study Hours/Day", f"{profile.study_hours_per_day}h")
    row("Deadline", f"{profile.deadline_months} months")
    row("Budget", profile.budget.value.title())
    row("Learning Style", ", ".join(profile.learning_preferences) or "—")
    if profile.constraints:
        row("Constraints", "\n".join(profile.constraints))

    console.print(table)


def render_progress_dashboard(
    roadmap: Roadmap,
    progress_map: dict[str, float],
) -> None:
    """Render a progress dashboard with per-phase bars."""

    console.print()
    for phase in roadmap.phases:
        if not phase.skills:
            continue
        total = sum(progress_map.get(s.id, 0.0) for s in phase.skills)
        pct = total / len(phase.skills)
        bar_width = 30
        filled = int(bar_width * pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        style = "phase_done" if pct >= 100 else ("phase_active" if pct > 0 else "phase_pending")
        console.print(
            f"  Phase {phase.phase_number:>2}  "
            f"[{style}]{bar}[/{style}]  "
            f"[dim]{pct:>5.1f}%[/dim]  {phase.name}"
        )
    console.print()
