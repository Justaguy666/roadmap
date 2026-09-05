"""Unit tests for SkillGraphBuilder and SkillGraphValidator."""

from __future__ import annotations

from roadmap.application.graph.builder import SkillGraphBuilder
from roadmap.domain.entities.skill import SkillDependency, SkillNode


def test_valid_dag_topological_sort() -> None:
    nodes = [
        SkillNode(name="C++"),
        SkillNode(name="Linear Algebra"),
        SkillNode(name="Game Architecture"),
    ]
    deps = [
        SkillDependency(prerequisite_skill="C++", dependent_skill="Game Architecture"),
        SkillDependency(prerequisite_skill="Linear Algebra", dependent_skill="Game Architecture"),
    ]

    node_list, _, val = SkillGraphBuilder.build(nodes, deps)
    assert val.is_valid is True
    assert len(val.cycles) == 0

    depth_map = {n.name: n.depth for n in node_list}
    assert depth_map["C++"] == 0
    assert depth_map["Linear Algebra"] == 0
    assert depth_map["Game Architecture"] == 1

    sorted_skills = val.topological_order
    c_idx = sorted_skills.index("C++")
    ga_idx = sorted_skills.index("Game Architecture")
    la_idx = sorted_skills.index("Linear Algebra")
    assert c_idx < ga_idx
    assert la_idx < ga_idx


def test_cycle_detection() -> None:
    nodes = [
        SkillNode(name="A"),
        SkillNode(name="B"),
        SkillNode(name="C"),
    ]
    deps = [
        SkillDependency(prerequisite_skill="A", dependent_skill="B"),
        SkillDependency(prerequisite_skill="B", dependent_skill="C"),
        SkillDependency(prerequisite_skill="C", dependent_skill="A"),  # Cycle!
    ]

    _, _, val = SkillGraphBuilder.build(nodes, deps)
    assert val.is_valid is False
    assert len(val.cycles) >= 1
    assert any("Cyclic dependency detected" in err for err in val.errors)


def test_self_dependency_detection() -> None:
    nodes = [SkillNode(name="Python")]
    deps = [SkillDependency(prerequisite_skill="Python", dependent_skill="Python")]

    _, _, val = SkillGraphBuilder.build(nodes, deps)
    assert val.is_valid is False
    assert any("Self-dependency detected" in err for err in val.errors)


def test_unknown_prerequisite_node_detection() -> None:
    nodes = [SkillNode(name="Unreal Engine")]
    deps = [SkillDependency(prerequisite_skill="C++", dependent_skill="Unreal Engine")]

    node_list, _, val = SkillGraphBuilder.build(nodes, deps)
    assert val.is_valid is False
    assert "C++" in val.unknown_nodes
    assert any("Unknown node references" in err for err in val.errors)

