"""
CLI command: `roadmap graph [--cycles] [--critical-path]`

Visualizes the skill prerequisite dependency DAG as a hierarchical tree or graph.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.tree import Tree

from roadmap.application.graph.builder import SkillGraphBuilder
from roadmap.cli.container import initialize_database
from roadmap.cli.display.console import console, print_error, print_header, print_info, print_warning
from roadmap.domain.entities.skill import SkillDependency, SkillNode
from roadmap.storage.database import get_session
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository

graph_app = typer.Typer(help="Visualize and validate skill prerequisite dependency DAG.")


@graph_app.callback(invoke_without_command=True)
def graph(
    show_cycles: Annotated[
        bool,
        typer.Option("--cycles", "-c", help="Check for and display dependency cycles only"),
    ] = False,
) -> None:
    """Render the Skill Prerequisite DAG tree and topological levels."""
    initialize_database()

    with get_session() as session:
        profile_repo = SqliteProfileRepository(session)
        roadmap_repo = SqliteRoadmapRepository(session)

        profile = profile_repo.load()
        if not profile:
            print_error("No profile found. Run `roadmap init` first.")
            raise typer.Exit(1)

        roadmap = roadmap_repo.load_latest(profile.id)
        if not roadmap:
            print_warning("No roadmap found. Run `roadmap generate` first.")
            raise typer.Exit(0)

        skills = roadmap.all_skills
        if not skills:
            print_warning("Current roadmap has no skills.")
            raise typer.Exit(0)

        # Build graph nodes and dependency edges
        nodes = [
            SkillNode(
                name=s.name,
                category=s.category,
                target_level=s.target_level,
                priority=s.priority,
                estimated_hours=s.estimated_hours,
                evidence_ids=s.evidence_ids,
                prerequisites=s.prerequisite_names,
            )
            for s in skills
        ]

        deps: list[SkillDependency] = []
        for s in skills:
            for p in s.prerequisite_names:
                deps.append(
                    SkillDependency(
                        prerequisite_skill=p,
                        dependent_skill=s.name,
                    )
                )

        built_nodes, norm_deps, val_result = SkillGraphBuilder.build(nodes, deps)
        depth_map = {n.name: n.depth for n in built_nodes}

        if show_cycles:
            if val_result.is_valid:
                print_info("No circular dependencies detected! Skill graph is a valid DAG.")
            else:
                print_error(f"Cycles detected ({len(val_result.cycles)}):")
                for c in val_result.cycles:
                    console.print(f"  [bold red]Cycle:[/bold red] {' -> '.join(c)}")
            return

        print_header(f"Skill Dependency Graph (DAG) — {roadmap.title} (v{roadmap.version})")
        if not val_result.is_valid:
            print_warning(f"Graph issues detected: {', '.join(val_result.errors)}")

        console.print(
            f"  [bold]Total Nodes:[/bold] {len(nodes)}  |  "
            f"[bold]Dependency Edges:[/bold] {len(deps)}  |  "
            f"[bold]DAG Valid:[/bold] [{'green' if val_result.is_valid else 'red'}]{val_result.is_valid}[/]"
        )
        console.print()

        # Render DAG as Rich Tree grouped by depth
        tree = Tree(
            f":star: [bold cyan]Skill Dependency Graph (DAG)[/] for [yellow]{profile.target_role or profile.target_goal}[/] (v{roadmap.version})"
        )

        depth_to_skills: dict[int, list[SkillNode]] = {}
        for n in nodes:
            d = depth_map.get(n.name, 0)
            depth_to_skills.setdefault(d, []).append(n)

        for d in sorted(depth_to_skills.keys()):
            tier_name = "Foundational Prerequisites (Depth 0)" if d == 0 else f"Applied Layer (Depth {d})"
            layer_branch = tree.add(f"[bold yellow]{tier_name}[/bold yellow]")
            for sk in depth_to_skills[d]:
                pri_color = "red" if sk.priority.value in ("critical", "high") else "green"
                ev_badge = f" [dim cyan]({len(sk.evidence_ids)} citations)[/dim cyan]" if sk.evidence_ids else ""
                sk_node = layer_branch.add(
                    f"[{pri_color}]●[/{pri_color}] [bold]{sk.name}[/bold] "
                    f"[dim]({sk.category}, {sk.estimated_hours:.0f}h)[/dim]{ev_badge}"
                )
                if sk.prerequisites:
                    for prereq in sk.prerequisites:
                        sk_node.add(f"[dim]requires:[/dim] [italic]{prereq}[/italic]")

        console.print(tree)
        console.print()
        print_info("Run [bold]roadmap why <skill>[/bold] to inspect decision weights and evidence for any skill.")
        console.print()
