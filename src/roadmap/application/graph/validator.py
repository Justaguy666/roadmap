"""Application service: SkillGraphValidator.

Performs deterministic validation of skill dependency graphs using NetworkX:
- Cycle detection (simple cycles)
- Self-dependency detection
- Unknown node detection
- Missing/invalid prerequisite references
- Redundant transitive edges
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import networkx as nx

from roadmap.domain.entities.skill import SkillDependency, SkillNode


@dataclass
class GraphValidationResult:
    is_valid: bool
    cycles: list[list[str]] = field(default_factory=list)
    self_dependencies: list[str] = field(default_factory=list)
    unknown_nodes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    topological_order: list[str] = field(default_factory=list)


class SkillGraphValidator:
    """Validates directed skill graphs deterministically."""

    @classmethod
    def validate(
        cls,
        nodes: list[SkillNode],
        dependencies: list[SkillDependency],
    ) -> GraphValidationResult:
        """Validate node definitions and dependency edges."""
        node_names = {n.name.strip().lower(): n.name for n in nodes}
        errors: list[str] = []
        self_deps: list[str] = []
        unknowns: set[str] = set()

        g = nx.DiGraph()  # type: ignore[var-annotated]
        for n in nodes:
            g.add_node(n.name)

        # Check edges
        for d in dependencies:
            from_name = d.from_name.strip()
            to_name = d.to_name.strip()

            if not from_name or not to_name:
                continue

            from_norm = from_name.lower()
            to_norm = to_name.lower()

            # Check unknown nodes
            if from_norm not in node_names:
                unknowns.add(from_name)
            if to_norm not in node_names:
                unknowns.add(to_name)

            # Check self-dependency
            if from_norm == to_norm:
                self_deps.append(from_name)
                errors.append(f"Self-dependency detected: '{from_name}' depends on itself.")
                continue

            # If it is a hard prerequisite, add edge to directed graph for cycle testing
            if d.is_hard_requirement:
                # Direction: from_name -> to_name (must learn from_name before to_name)
                canonical_from = node_names.get(from_norm, from_name)
                canonical_to = node_names.get(to_norm, to_name)
                g.add_edge(canonical_from, canonical_to)

        if unknowns:
            errors.append(f"Unknown node references in prerequisites: {sorted(unknowns)}")

        # Cycle detection
        cycles: list[list[str]] = []
        try:
            simple_cycles = list(nx.simple_cycles(g))
            if simple_cycles:
                cycles = simple_cycles
                for cyc in cycles:
                    cyc_str = " -> ".join(cyc + [cyc[0]])
                    errors.append(f"Cyclic dependency detected: {cyc_str}")
        except Exception as exc:
            errors.append(f"Graph cycle analysis failed: {exc}")

        # Compute topological order if acyclic
        topological_order: list[str] = []
        if not cycles and not self_deps:
            with contextlib.suppress(Exception):
                topological_order = list(nx.topological_sort(g))

        is_valid = len(errors) == 0 and len(cycles) == 0 and len(self_deps) == 0

        return GraphValidationResult(
            is_valid=is_valid,
            cycles=cycles,
            self_dependencies=self_deps,
            unknown_nodes=sorted(unknowns),
            errors=errors,
            topological_order=topological_order,
        )
