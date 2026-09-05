"""Application service: SkillGraphBuilder.

Builds and cleans directed acyclic skill graphs from proposals and skill definitions:
- Canonical skill name normalization
- Deduplication of nodes and edges
- Verification of referenced nodes
- Assignment of topological layer/depth
"""

from __future__ import annotations

import networkx as nx

from roadmap.application.graph.validator import GraphValidationResult, SkillGraphValidator
from roadmap.domain.entities.skill import SkillDependency, SkillNode


class SkillGraphBuilder:
    """Builds, normalizes, and layers skill dependency graphs."""

    @classmethod
    def build(
        cls,
        nodes: list[SkillNode],
        dependencies: list[SkillDependency],
    ) -> tuple[list[SkillNode], list[SkillDependency], GraphValidationResult]:
        """Normalize nodes and edges, validate graph, and assign depths."""
        # 1. Deduplicate and normalize nodes
        unique_nodes: dict[str, SkillNode] = {}
        for n in nodes:
            norm = n.name.strip().lower()
            if norm not in unique_nodes:
                unique_nodes[norm] = n.model_copy()

        # 2. Normalize edges and filter duplicates
        normalized_deps: list[SkillDependency] = []
        seen_edges: set[tuple[str, str, str]] = set()

        for d in dependencies:
            f_norm = d.from_name.strip().lower()
            t_norm = d.to_name.strip().lower()

            if not f_norm or not t_norm:
                continue

            edge_key = (f_norm, t_norm, d.dependency_type.value)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            # Match to canonical node names if present
            canonical_from = unique_nodes[f_norm].name if f_norm in unique_nodes else d.from_name.strip()
            canonical_to = unique_nodes[t_norm].name if t_norm in unique_nodes else d.to_name.strip()

            dep_copy = d.model_copy()
            dep_copy.prerequisite_skill = canonical_from
            dep_copy.dependent_skill = canonical_to
            normalized_deps.append(dep_copy)

        node_list = list(unique_nodes.values())
        val_result = SkillGraphValidator.validate(node_list, normalized_deps)

        # 3. If valid, compute topological depths
        if val_result.is_valid:
            g = nx.DiGraph()  # type: ignore[var-annotated]
            for n in node_list:
                g.add_node(n.name)
            for d in normalized_deps:
                if d.is_hard_requirement:
                    g.add_edge(d.from_name, d.to_name)

            for n in node_list:
                # Depth = longest path from any root node to n
                ancestors = nx.ancestors(g, n.name)
                if not ancestors:
                    n.depth = 0
                else:
                    # Compute max path length among ancestors
                    depth = 0
                    for anc in ancestors:
                        try:
                            paths = list(nx.all_simple_paths(g, source=anc, target=n.name))
                            if paths:
                                depth = max(depth, max(len(p) - 1 for p in paths))
                        except Exception:
                            pass
                    n.depth = depth

                # Also populate node.prerequisites
                prereqs = list(g.predecessors(n.name))
                n.prerequisites = sorted(prereqs)

        return node_list, normalized_deps, val_result
