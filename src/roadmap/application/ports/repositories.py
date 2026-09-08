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
    EmbeddingRecord,
    Evidence,
    Goal,
    KnowledgeChunk,
    KnowledgeDocument,
    LearningFeedback,
    ProgressRecord,
    Recommendation,
    ResearchRun,
    Roadmap,
    RoadmapAdaptation,
    Skill,
    SkillDependency,
    Source,
    User,
    UserProfile,
)


class UserRepository(Protocol):
    """Persistence port for user accounts."""

    def save(self, user: User) -> None:
        """Create or update a user."""
        ...

    def get_by_id(self, user_id: str) -> User | None:
        """Load a user by unique identifier."""
        ...

    def get_by_email(self, email: str) -> User | None:
        """Load a user by normalized email address."""
        ...


class ProfileRepository(Protocol):
    """Persistence port for user profiles."""

    def save(self, profile: UserProfile) -> None:
        """Create or update a profile."""
        ...

    def load(self) -> UserProfile | None:
        """Load the current active profile (single-user MVP / CLI compatibility)."""
        ...

    def load_by_id(self, profile_id: str) -> UserProfile | None:
        """Load a profile by its ID."""
        ...

    def load_by_user_id(self, user_id: str) -> list[UserProfile]:
        """Load all profiles owned by a specific user."""
        ...

    def load_for_user(self, user_id: str, profile_id: str) -> UserProfile | None:
        """Load a specific profile owned by a specific user."""
        ...

    def delete(self, profile_id: str | None = None) -> None:
        """Delete profile (or all profiles if profile_id is None)."""
        ...

    def exists(self) -> bool:
        """Return True if any profile exists."""
        ...

    def exists_for_user(self, user_id: str) -> bool:
        """Return True if the given user already owns a profile."""
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

    def load_by_version(self, profile_id: str, version: int) -> Roadmap | None:
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

    def get_by_id(self, source_id: str) -> Source | None:
        ...

    def get_by_url(self, url: str) -> Source | None:
        ...

    def load_by_url(self, url: str) -> Source | None:
        ...

    def list_all(self, limit: int = 100) -> list[Source]:
        ...

    def load_all(self, profile_id: str | None = None) -> list[Source]:
        ...


class EvidenceRepository(Protocol):
    """Persistence port for evidence items."""

    def save(self, evidence: Evidence) -> None:
        ...

    def get_by_id(self, evidence_id: str) -> Evidence | None:
        ...

    def find_by_skill(self, skill_name: str) -> list[Evidence]:
        ...

    def load_for_skill(self, skill_id: str) -> list[Evidence]:
        ...

    def load_for_recommendation(self, recommendation_id: str) -> list[Evidence]:
        ...

    def list_all(self, limit: int = 100) -> list[Evidence]:
        ...


class RecommendationRepository(Protocol):
    """Persistence port for recommendations."""

    def save(self, recommendation: Recommendation) -> None:
        ...

    def load_for_skill(self, skill_id: str, roadmap_id: str) -> Recommendation | None:
        ...

    def find_by_skill(self, skill_id: str) -> list[Recommendation]:
        ...

    def find_by_skill_name_or_id(self, skill_name_or_id: str, roadmap_id: str | None = None) -> Recommendation | None:
        ...

    def list_by_roadmap(self, roadmap_id: str) -> list[Recommendation]:
        ...

    def load_for_roadmap(self, roadmap_id: str) -> list[Recommendation]:
        ...


class ResearchRunRepository(Protocol):
    """Persistence port for research runs."""

    def save(self, run: ResearchRun) -> None:
        ...

    def get_latest(self, profile_id: str | None = None) -> ResearchRun | None:
        ...

    def get_by_id(self, run_id: str) -> ResearchRun | None:
        ...


class FeedbackRepository(Protocol):
    """Persistence port for learning feedback."""

    def save(self, feedback: LearningFeedback) -> None:
        ...

    def load_for_roadmap(self, roadmap_id: str) -> list[LearningFeedback]:
        ...

    def load_for_skill(self, roadmap_id: str, skill_id: str) -> list[LearningFeedback]:
        ...


class AdaptationRepository(Protocol):
    """Persistence port for roadmap adaptations."""

    def save(self, adaptation: RoadmapAdaptation) -> None:
        ...

    def load_for_profile(self, profile_id: str) -> list[RoadmapAdaptation]:
        ...

    def load_by_version(self, profile_id: str, new_version: int) -> RoadmapAdaptation | None:
        ...

    def get_latest_adaptation(self, profile_id: str) -> RoadmapAdaptation | None:
        ...


class KnowledgeRepository(Protocol):
    """Persistence port for knowledge documents, chunks, and embeddings."""

    def save_document(self, document: KnowledgeDocument) -> None:
        ...

    def get_document_by_id(self, document_id: str) -> KnowledgeDocument | None:
        ...

    def get_document_by_evidence_id(self, evidence_id: str) -> KnowledgeDocument | None:
        ...

    def list_all_documents(self, limit: int = 1000) -> list[KnowledgeDocument]:
        ...

    def delete_document(self, document_id: str) -> None:
        ...

    def save_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        ...

    def get_chunk_by_id(self, chunk_id: str) -> KnowledgeChunk | None:
        ...

    def list_chunks_for_document(self, document_id: str) -> list[KnowledgeChunk]:
        ...

    def count_chunks(self) -> int:
        ...

    def count_documents(self) -> int:
        ...

    def save_embeddings(self, records: list[EmbeddingRecord]) -> None:
        ...

    def get_embedding_by_chunk_id(self, chunk_id: str) -> EmbeddingRecord | None:
        ...

    def list_all_embeddings(self, limit: int = 5000) -> list[EmbeddingRecord]:
        ...

    def count_embeddings(self) -> int:
        ...


__all__ = [
    "AdaptationRepository",
    "EvidenceRepository",
    "FeedbackRepository",
    "GoalRepository",
    "KnowledgeRepository",
    "ProfileRepository",
    "ProgressRepository",
    "RecommendationRepository",
    "ResearchRunRepository",
    "RoadmapRepository",
    "SkillRepository",
    "SourceRepository",
]
