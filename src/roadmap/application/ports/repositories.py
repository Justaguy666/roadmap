"""
Application ports: Repository interfaces.

All repositories are Protocol classes — structural typing.
Infrastructure implementations provide the concrete classes.

IMPORTANT: Domain logic must depend ONLY on these protocols,
never on SQLAlchemy, SQLite, or any other persistence technology.
"""

from __future__ import annotations

from typing import Protocol

from roadmap.domain.entities import (
    Evidence,
    Goal,
    ProgressRecord,
    Recommendation,
    Roadmap,
    Skill,
    SkillDependency,
    Source,
    UserProfile,
)


class ProfileRepository(Protocol):
    """Persistence port for user profiles."""

    def save(self, profile: UserProfile) -> None:
        """Create or update a profile."""
        ...

    def load(self) -> UserProfile | None:
        """Load the current active profile (single-user MVP)."""
        ...

    def delete(self) -> None:
        """Delete the current profile and all associated data."""
        ...

    def exists(self) -> bool:
        """Return True if a profile exists."""
        ...


class GoalRepository(Protocol):
    """Persistence port for goals."""

    def save(self, goal: Goal) -> None:
        ...

    def load(self, profile_id: str) -> Goal | None:
        ...


class SkillRepository(Protocol):
    """Persistence port for skills and skill dependencies."""

    def save_skill(self, skill: Skill) -> None:
        ...

    def save_skills(self, skills: list[Skill]) -> None:
        ...

    def load_skills(self, profile_id: str) -> list[Skill]:
        ...

    def load_skill_by_name(self, profile_id: str, name: str) -> Skill | None:
        ...

    def save_dependency(self, dependency: SkillDependency) -> None:
        ...

    def save_dependencies(self, dependencies: list[SkillDependency]) -> None:
        ...

    def load_dependencies(self, profile_id: str) -> list[SkillDependency]:
        ...

    def delete_all(self, profile_id: str) -> None:
        ...


class RoadmapRepository(Protocol):
    """Persistence port for roadmaps."""

    def save(self, roadmap: Roadmap) -> None:
        ...

    def load_latest(self, profile_id: str) -> Roadmap | None:
        ...

    def load_all(self, profile_id: str) -> list[Roadmap]:
        ...

    def delete(self, roadmap_id: str) -> None:
        ...


class ProgressRepository(Protocol):
    """Persistence port for progress records."""

    def save(self, record: ProgressRecord) -> None:
        ...

    def load_all(self, profile_id: str) -> list[ProgressRecord]:
        ...

    def load_for_skill(self, profile_id: str, skill_id: str) -> ProgressRecord | None:
        ...

    def delete_all(self, profile_id: str) -> None:
        ...


class SourceRepository(Protocol):
    """Persistence port for research sources."""

    def save(self, source: Source) -> None:
        ...

    def load_by_url(self, url: str) -> Source | None:
        ...

    def load_all(self, profile_id: str) -> list[Source]:
        ...


class EvidenceRepository(Protocol):
    """Persistence port for evidence items."""

    def save(self, evidence: Evidence) -> None:
        ...

    def load_for_skill(self, skill_id: str) -> list[Evidence]:
        ...

    def load_for_recommendation(self, recommendation_id: str) -> list[Evidence]:
        ...


class RecommendationRepository(Protocol):
    """Persistence port for recommendations."""

    def save(self, recommendation: Recommendation) -> None:
        ...

    def load_for_skill(self, skill_id: str, roadmap_id: str) -> Recommendation | None:
        ...

    def load_for_roadmap(self, roadmap_id: str) -> list[Recommendation]:
        ...
