"""
Deterministic FakeLLMProvider for offline testing and verification.

Allows tests to verify application use cases and CLI flows
without external network access or API credentials.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from roadmap.agents.schemas.goal_analysis import (
    CompetencyDraft,
    GoalAnalysisResult,
    OptionalSkillDraft,
    RequiredSkillDraft,
)
from roadmap.agents.schemas.roadmap_generation import (
    RoadmapGenerationResult,
    RoadmapMilestoneDraft,
    RoadmapPhaseDraft,
    RoadmapProjectDraft,
    RoadmapResourceDraft,
    RoadmapSkillDraft,
)
from roadmap.application.ports.llm_provider import (
    LLMMessage,
    LLMProvider,
    LLMValidationError,
)
from roadmap.domain.value_objects.enums import Priority, ResourceType, SkillLevel

T = TypeVar("T", bound=BaseModel)


def get_default_fake_goal_analysis() -> GoalAnalysisResult:
    """Generate a realistic, deterministic GoalAnalysisResult for testing."""
    return GoalAnalysisResult(
        interpreted_goal="Master software engineering fundamentals and build game systems",
        target_role="Gameplay Programmer",
        competencies=[
            CompetencyDraft(
                name="Core Systems & Programming",
                category="programming",
                importance_score=0.95,
                description="Low-level memory management and modern C++",
                skill_names=["C++", "Memory Management", "Data Structures"],
            ),
            CompetencyDraft(
                name="Mathematics for Games",
                category="mathematics",
                importance_score=0.85,
                description="3D linear algebra and basic physics calculations",
                skill_names=["Linear Algebra", "Vector Math"],
            ),
            CompetencyDraft(
                name="Game Architecture & Loops",
                category="game engine",
                importance_score=0.90,
                description="Engine architecture, update cycles, and entity patterns",
                skill_names=["Game Loop", "Entity Component System"],
            ),
        ],
        required_skills=[
            RequiredSkillDraft(
                name="C++",
                category="programming",
                target_level=SkillLevel.PROFICIENT,
                priority=Priority.CRITICAL,
                description="Modern C++ (17/20), pointers, RAII, move semantics",
                rationale="Standard industry programming language for game engines",
            ),
            RequiredSkillDraft(
                name="Data Structures",
                category="algorithms",
                target_level=SkillLevel.PROFICIENT,
                priority=Priority.HIGH,
                description="Arrays, vectors, spatial trees, hashing",
                rationale="Essential for runtime performance and memory cache locality",
            ),
            RequiredSkillDraft(
                name="Linear Algebra",
                category="mathematics",
                target_level=SkillLevel.PROFICIENT,
                priority=Priority.HIGH,
                description="Matrix transformations, quaternions, dot/cross products",
                rationale="Underpins all 3D gameplay math and camera systems",
            ),
            RequiredSkillDraft(
                name="Game Loop & Architecture",
                category="game engine",
                target_level=SkillLevel.PROFICIENT,
                priority=Priority.HIGH,
                description="Fixed/variable timestep, state management, decoupling",
                rationale="Core structural backbone of every game runtime",
            ),
            RequiredSkillDraft(
                name="Git & Version Control",
                category="tools",
                target_level=SkillLevel.FAMILIAR,
                priority=Priority.MEDIUM,
                description="Branching, rebasing, collaboration",
                rationale="Essential workflow hygiene",
            ),
        ],
        optional_skills=[
            OptionalSkillDraft(
                name="Shaders & HLSL",
                category="computer graphics",
                rationale="Differentiates candidate for technical gameplay roles",
            ),
        ],
        assumptions=[
            "User targets internship/junior-level gameplay engineering",
            "Modern C++ is the primary programming language",
        ],
        confidence=0.92,
    )


def get_default_fake_roadmap_result() -> RoadmapGenerationResult:
    """Generate a realistic, deterministic RoadmapGenerationResult for testing."""
    return RoadmapGenerationResult(
        roadmap_objective="Progress from programming baseline to production-ready gameplay programmer",
        phases=[
            RoadmapPhaseDraft(
                phase_name="Phase 1: Modern C++ & Systems Foundations",
                objective="Master modern C++ mechanics, pointer ownership, and memory layout",
                estimated_duration_weeks=6.0,
                priority=Priority.HIGH,
                skills=[
                    RoadmapSkillDraft(
                        name="C++",
                        category="programming",
                        target_level=SkillLevel.PROFICIENT,
                        priority=Priority.CRITICAL,
                        prerequisites=[],
                        estimated_hours=60.0,
                    ),
                    RoadmapSkillDraft(
                        name="Git & Version Control",
                        category="tools",
                        target_level=SkillLevel.FAMILIAR,
                        priority=Priority.MEDIUM,
                        prerequisites=[],
                        estimated_hours=15.0,
                    ),
                ],
                projects=[
                    RoadmapProjectDraft(
                        title="Custom Memory Arena Allocator",
                        description="Implement a stack/arena allocator with linear allocation and block resets",
                        skills_practiced=["C++", "Memory Management"],
                        difficulty=SkillLevel.FAMILIAR,
                        expected_outcome="Benchmarked C++ allocator demonstrating zero-fragmentation speedup",
                        portfolio_value=0.75,
                        estimated_hours=20.0,
                    )
                ],
                milestones=[
                    RoadmapMilestoneDraft(
                        measurable_outcome="Can write RAII-compliant modern C++ with zero memory leaks",
                        exit_criteria=[
                            "Passes address sanitizer with zero leaks",
                            "Completed custom allocator with test suite",
                        ],
                        estimated_weeks=1.0,
                    )
                ],
                resources=[
                    RoadmapResourceDraft(
                        title="Effective Modern C++",
                        resource_type=ResourceType.BOOK,
                        url="https://example.com/modern-cpp",
                        provider="O'Reilly",
                        difficulty=SkillLevel.FAMILIAR,
                        estimated_hours=25.0,
                    )
                ],
            ),
            RoadmapPhaseDraft(
                phase_name="Phase 2: Game Math & Architecture",
                objective="Apply linear algebra and entity architectures to build interactive game systems",
                estimated_duration_weeks=8.0,
                priority=Priority.HIGH,
                skills=[
                    RoadmapSkillDraft(
                        name="Linear Algebra",
                        category="mathematics",
                        target_level=SkillLevel.PROFICIENT,
                        priority=Priority.HIGH,
                        prerequisites=["C++"],
                        estimated_hours=45.0,
                    ),
                    RoadmapSkillDraft(
                        name="Data Structures",
                        category="algorithms",
                        target_level=SkillLevel.PROFICIENT,
                        priority=Priority.HIGH,
                        prerequisites=["C++"],
                        estimated_hours=40.0,
                    ),
                    RoadmapSkillDraft(
                        name="Game Loop & Architecture",
                        category="game engine",
                        target_level=SkillLevel.PROFICIENT,
                        priority=Priority.HIGH,
                        prerequisites=["C++", "Linear Algebra"],
                        estimated_hours=45.0,
                    ),
                ],
                projects=[
                    RoadmapProjectDraft(
                        title="2D Physics Game Prototype",
                        description="Build a playable 2D game from scratch using SDL2 with custom vector math and collision",
                        skills_practiced=["C++", "Linear Algebra", "Game Loop & Architecture"],
                        difficulty=SkillLevel.LEARNING,
                        expected_outcome="Playable desktop game showing smooth movement and physics simulation",
                        portfolio_value=0.85,
                        estimated_hours=35.0,
                    )
                ],
                milestones=[
                    RoadmapMilestoneDraft(
                        measurable_outcome="Solid grasp of vector math and fixed timestep loops",
                        exit_criteria=[
                            "Working 2D game running at deterministic 60 FPS",
                            "Collision detection working without jitter",
                        ],
                        estimated_weeks=1.0,
                    )
                ],
            ),
        ],
        assumptions=[
            "Assumes 15 to 20 hours per week dedicated study",
            "Focuses on native C++ without heavyweight commercial engines in foundational phases",
        ],
        total_estimated_weeks=14.0,
    )


class FakeLLMProvider(LLMProvider):
    """
    Fake LLM provider returning predetermined schemas for testing.
    """

    def __init__(
        self,
        goal_analysis_result: GoalAnalysisResult | None = None,
        roadmap_result: RoadmapGenerationResult | None = None,
        simulate_error: Exception | None = None,
    ) -> None:
        self.goal_analysis_result = goal_analysis_result or get_default_fake_goal_analysis()
        self.roadmap_result = roadmap_result or get_default_fake_roadmap_result()
        self.simulate_error = simulate_error
        self.calls: list[dict[str, Any]] = []

    def set_goal_analysis(self, result: GoalAnalysisResult) -> None:
        self.goal_analysis_result = result

    def set_roadmap_result(self, result: RoadmapGenerationResult) -> None:
        self.roadmap_result = result

    def complete(
        self,
        messages: list[LLMMessage],
        response_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        self.calls.append({
            "type": "structured",
            "response_model": response_model.__name__,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        })

        if self.simulate_error:
            raise self.simulate_error

        if response_model is GoalAnalysisResult or issubclass(response_model, GoalAnalysisResult):
            return self.goal_analysis_result  # type: ignore[return-value]

        if response_model is RoadmapGenerationResult or issubclass(response_model, RoadmapGenerationResult):
            return self.roadmap_result  # type: ignore[return-value]

        # Research-specific models
        from roadmap.agents.schemas.research import (
            EvidenceExtractionResult,
            ExtractedClaimDraft,
            ResearchPlan,
            ResearchQuery,
        )

        if response_model is ResearchPlan or issubclass(response_model, ResearchPlan):
            return ResearchPlan(  # type: ignore[return-value]
                topic="Gameplay Programmer",
                target_market="Vietnam, Japan",
                queries=[
                    ResearchQuery(query="gameplay programmer C++ requirements", query_type="market", focus="C++"),
                    ResearchQuery(query="Unreal Engine 5 gameplay architecture documentation", query_type="resource", focus="Unreal Engine"),
                    ResearchQuery(query="game math 3D linear algebra course", query_type="resource", focus="Linear Algebra"),
                ],
            )

        if response_model is EvidenceExtractionResult or issubclass(response_model, EvidenceExtractionResult):
            return EvidenceExtractionResult(  # type: ignore[return-value]
                source_title="Gameplay Engineering Requirements & Architecture",
                detected_source_type="job_posting",
                claims=[
                    ExtractedClaimDraft(
                        claim="Requires modern C++ (C++17/20), strong 3D math and pointer mastery.",
                        related_skills=["C++", "Linear Algebra"],
                        source_type="job_posting",
                        confidence=0.9,
                        relevance=0.95,
                    ),
                    ExtractedClaimDraft(
                        claim="Demonstrated experience architecting gameplay components in Unreal Engine 5.",
                        related_skills=["Unreal Engine", "Game Loop & Architecture"],
                        source_type="job_posting",
                        confidence=0.88,
                        relevance=0.92,
                    ),
                ],
            )

        # Generic fallback if custom model passed
        try:
            return response_model()  # type: ignore[call-arg]
        except Exception as e:
            raise LLMValidationError(
                model_name=response_model.__name__,
                attempts=1,
                last_error=f"Cannot instantiate default {response_model.__name__}: {e}",
            ) from e

    def complete_text(
        self,
        messages: list[LLMMessage],
        temperature: float | None = None,
    ) -> str:
        self.calls.append({
            "type": "text",
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
        })

        if self.simulate_error:
            raise self.simulate_error

        return "This is a deterministic fake completion explanation."
