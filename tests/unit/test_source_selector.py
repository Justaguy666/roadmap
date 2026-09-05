"""
Unit tests for deterministic SourceSelector and diversity filters.
"""

from __future__ import annotations

from roadmap.application.ports.search_provider import SearchResult
from roadmap.domain.services.source_selector import SourceSelector


def test_select_sources_respects_max_budget() -> None:
    results = [
        SearchResult(
            url=f"https://domain{i}.com/job/{i}",
            title=f"Game Programmer {i}",
            snippet="C++ programming requirements",
            domain=f"domain{i}.com",
            score=0.8,
        )
        for i in range(25)
    ]

    selected = SourceSelector.select_sources(
        results=results,
        target_role="Game Programmer",
        focus_skills=["C++"],
        max_sources=10,
    )

    assert len(selected) == 10


def test_select_sources_caps_repeated_domains() -> None:
    # 10 results from same job board, 5 from different authoritative docs
    same_board_results = [
        SearchResult(
            url=f"https://aggregator.com/jobs/{i}",
            title=f"Gameplay Programmer Job {i}",
            snippet="C++ and Unreal",
            domain="aggregator.com",
            score=0.9,
        )
        for i in range(10)
    ]
    other_results = [
        SearchResult(
            url=f"https://docs.unrealengine.com/article/{i}",
            title=f"Unreal Gameplay Documentation {i}",
            snippet="Engine architecture and game loop",
            domain="docs.unrealengine.com",
            score=0.7,
        )
        for i in range(5)
    ]
    all_results = same_board_results + other_results

    selected = SourceSelector.select_sources(
        results=all_results,
        target_role="Gameplay Programmer",
        focus_skills=["C++", "Unreal Engine"],
        max_sources=8,
        max_per_domain=3,
    )

    aggregator_count = sum(1 for r in selected if "aggregator.com" in r.url)
    assert aggregator_count <= 3
    assert any("docs.unrealengine.com" in r.url for r in selected)


def test_select_sources_prioritizes_role_and_authority() -> None:
    doc_res = SearchResult(
        url="https://docs.unrealengine.com/en-US/ProgrammingAndScripting/",
        title="Unreal Engine Programming Guide",
        snippet="Official C++ architecture and memory management",
        domain="docs.unrealengine.com",
        score=0.8,
    )
    unrelated_res = SearchResult(
        url="https://randomblog.xyz/post/123",
        title="My thoughts on coffee",
        snippet="Random morning thoughts",
        domain="randomblog.xyz",
        score=0.1,
    )

    selected = SourceSelector.select_sources(
        results=[unrelated_res, doc_res],
        target_role="Gameplay Programmer",
        focus_skills=["C++"],
        max_sources=1,
    )

    assert len(selected) == 1
    assert selected[0].url == doc_res.url
