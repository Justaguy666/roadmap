"""
FakeSearchProvider: Deterministic search double for testing and offline execution.
"""

from __future__ import annotations

from roadmap.application.ports.search_provider import SearchProvider, SearchResponse, SearchResult


class FakeSearchProvider(SearchProvider):
    """Deterministic in-memory search provider."""

    def __init__(self, canned_results: dict[str, list[SearchResult]] | None = None) -> None:
        self.canned_results = canned_results or {}
        self.queries_executed: list[str] = []

    def search(
        self,
        query: str,
        max_results: int = 10,
        include_full_content: bool = False,  # noqa: ARG002
    ) -> SearchResponse:
        self.queries_executed.append(query)

        # Check for specific canned match
        for key, results in self.canned_results.items():
            if key.lower() in query.lower():
                return SearchResponse(
                    query=query,
                    results=results[:max_results],
                    total_found=len(results),
                    provider="fake",
                )

        # Default fallback results
        default_results = [
            SearchResult(
                url="https://docs.unrealengine.com/5.4/en-US/gameplay-architecture/",
                title="Gameplay Architecture | Unreal Engine 5.4 Documentation",
                snippet="Learn the core C++ gameplay classes in Unreal Engine: Actors, Components, GameModes.",
                domain="docs.unrealengine.com",
                score=0.95,
                content="Unreal Engine gameplay architecture relies on C++ Actors, Pawn, Character, and ActorComponents.",
            ),
            SearchResult(
                url="https://careers.epicgames.com/jobs/gameplay-programmer",
                title="Gameplay Programmer - Epic Games Careers",
                snippet="We are seeking a Gameplay Programmer with strong C++, 3D math (linear algebra), and multiplayer experience.",
                domain="epicgames.com",
                score=0.92,
                content="Requirements: 3+ years modern C++, Unreal Engine, network replication, physics, linear algebra.",
            ),
            SearchResult(
                url="https://www.gamedeveloper.com/programming/modern-cpp-in-game-dev",
                title="Modern C++ Standards in Game Development",
                snippet="Industry survey showing 85% of studio codebases utilizing C++17 or C++20 for performance-critical systems.",
                domain="gamedeveloper.com",
                score=0.88,
                content="Modern game programming emphasizes C++17/20, cache efficiency, data-oriented design, and memory management.",
            ),
            SearchResult(
                url="https://ocw.mit.edu/courses/electrical-engineering-and-computer-science/",
                title="MIT OpenCourseWare - Introduction to C++",
                snippet="Rigorous academic curriculum covering pointers, references, memory layout, and object-oriented design in C++.",
                domain="ocw.mit.edu",
                score=0.90,
                content="MIT 6.096 curriculum covers pointers, dynamic memory, memory leaks, RAII, and templates.",
            ),
        ]

        return SearchResponse(
            query=query,
            results=default_results[:max_results],
            total_found=len(default_results),
            provider="fake",
        )

    def search_similar(
        self,
        url: str,
        max_results: int = 5,
    ) -> SearchResponse:
        return self.search(url, max_results=max_results)
