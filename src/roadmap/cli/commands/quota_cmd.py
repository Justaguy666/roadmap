"""
CLI command: `roadmap quota [--json]`

Displays current LLM application budget allocations, usage records,
and upstream provider health/cooldown status.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import typer
from rich.panel import Panel
from rich.table import Table

from roadmap.cli.container import get_budget_context, initialize_database
from roadmap.cli.display.console import console
from roadmap.config.settings import settings

quota_app = typer.Typer(help="Inspect LLM application budget, usage, and provider health status.")


@quota_app.callback(invoke_without_command=True)
def quota(
    as_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output quota and budget status in JSON format",
    ),
) -> None:
    """Display application LLM request budgets, workflow allocations, and provider health."""
    initialize_database()

    with get_budget_context() as budget_mgr:
        status = budget_mgr.get_quota_status()

    if as_json:
        data = {
            "timestamp": status.timestamp.isoformat(),
            "date": status.timestamp.strftime("%Y-%m-%d"),
            "global_budget": {
                "allocated": status.global_budget.allocated,
                "used": status.global_budget.used,
                "reserved": status.global_budget.reserved,
                "remaining": status.global_budget.remaining,
            },
            "workflow_budgets": {
                wf.value: {
                    "allocated": alloc.allocated,
                    "used": alloc.used,
                    "reserved": alloc.reserved,
                    "remaining": alloc.remaining,
                }
                for wf, alloc in status.workflow_budgets.items()
            },
            "provider_states": [
                {
                    "provider": p.provider,
                    "model": p.model,
                    "is_available": p.is_available,
                    "last_failure_category": p.last_failure_category.value if p.last_failure_category else None,
                    "last_failure_at": p.last_failure_at.isoformat() if p.last_failure_at else None,
                    "cooldown_until": p.cooldown_until.isoformat() if p.cooldown_until else None,
                    "error_message": p.error_message,
                }
                for p in status.provider_states
            ],
            "recent_usage": [
                {
                    "timestamp": u.timestamp.isoformat(),
                    "workflow": u.workflow.value,
                    "provider": u.provider,
                    "model": u.model,
                    "operation": u.operation,
                    "success": u.success,
                    "failure_category": u.failure_category.value if u.failure_category else None,
                    "actual_requests": u.actual_requests,
                }
                for u in status.recent_usage
            ],
        }
        console.print(json.dumps(data, indent=2))
        return

    # Rich Pretty UI
    console.print()
    today_str = status.timestamp.strftime("%Y-%m-%d")

    # 1. Application Global Budget
    g = status.global_budget
    rem_color = "green" if g.remaining > 3 else ("yellow" if g.remaining > 0 else "red")
    app_budget_text = (
        f"• [bold]Global Limit:[/bold] {g.allocated}\n"
        f"• [bold]Used Today:[/bold] {g.used}\n"
        f"• [bold]Active Pending:[/bold] {g.reserved}\n"
        f"• [bold]Remaining:[/bold] [{rem_color}]{g.remaining}[/{rem_color}]"
    )

    console.print(
        Panel(
            app_budget_text,
            title=f"[bold cyan]LLM Application Budget ({today_str})[/bold cyan]",
            border_style="cyan",
        )
    )

    # 2. Workflow Budgets Table
    wf_table = Table(title="Workflow Allocations (Daily)", border_style="dim")
    wf_table.add_column("Workflow", style="bold white")
    wf_table.add_column("Allocated", justify="center")
    wf_table.add_column("Used", justify="center")
    wf_table.add_column("Remaining", justify="center")

    for wf, alloc in status.workflow_budgets.items():
        w_color = "green" if alloc.remaining > 1 else ("yellow" if alloc.remaining > 0 else "red")
        wf_table.add_row(
            wf.value.capitalize(),
            str(alloc.allocated),
            str(alloc.used),
            f"[{w_color}]{alloc.remaining}[/{w_color}]",
        )
    console.print(wf_table)
    console.print()

    # 3. Provider Status Table
    prov_table = Table(title="Upstream Provider Health & Status", border_style="dim")
    prov_table.add_column("Provider", style="bold white")
    prov_table.add_column("Model")
    prov_table.add_column("Status", justify="center")
    prov_table.add_column("Last Failure / Cooldown")

    if not status.provider_states:
        curr_p = settings.llm_provider
        curr_m = (
            settings.llm_model
            or (settings.gemini_model if curr_p == "gemini" else (settings.openai_model if curr_p == "openai" else "mock"))
        )
        prov_table.add_row(curr_p.capitalize(), curr_m, "[green]ACTIVE / READY[/green]", "None")
    else:
        for p in status.provider_states:
            now = datetime.now(UTC)
            cd_until = (
                p.cooldown_until
                if (p.cooldown_until is None or p.cooldown_until.tzinfo)
                else p.cooldown_until.replace(tzinfo=UTC)
                if p.cooldown_until
                else None
            )
            in_cd = cd_until is not None and now < cd_until
            if in_cd:
                p_status = "[bold red]DAILY QUOTA EXCEEDED[/bold red]"
                cd_rem = int((cd_until - now).total_seconds()) if cd_until else 0
                detail = f"Cooldown {cd_rem}s remaining"
            elif not p.is_available:
                p_status = "[bold yellow]UNAVAILABLE[/bold yellow]"
                detail = p.last_failure_category.value if p.last_failure_category else "Error"
            else:
                p_status = "[green]AVAILABLE[/green]"
                detail = "Clear"
            prov_table.add_row(p.provider.capitalize(), p.model, p_status, detail)
    console.print(prov_table)
    console.print()

    # 4. Recent Usage Table
    if status.recent_usage:
        usage_table = Table(title="Recent LLM Requests", border_style="dim")
        usage_table.add_column("Time", style="dim")
        usage_table.add_column("Workflow")
        usage_table.add_column("Operation")
        usage_table.add_column("Reqs", justify="center")
        usage_table.add_column("Outcome", justify="center")

        for u in status.recent_usage[:8]:
            t_str = u.timestamp.strftime("%H:%M:%S")
            outcome = (
                "[green]SUCCESS[/green]"
                if u.success
                else f"[red]{u.failure_category.value if u.failure_category else 'FAILED'}[/red]"
            )
            usage_table.add_row(
                t_str,
                u.workflow.value,
                u.operation,
                str(u.actual_requests),
                outcome,
            )
        console.print(usage_table)
        console.print()
