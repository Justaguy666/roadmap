"""Domain entities: Skill and SkillDependency.

Skills are the fundamental units of the roadmap.
SkillDependencies form the prerequisite graph.

Important architectural note:
  The domain defines the *model* of skills and dependencies.
  The actual graph algorithms (topological sort, cycle detection)
  live in the application layer using NetworkX — they are NOT
  part of the domain to keep the domain free of library deps.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from roadmap.domain.value_objects import (
    DependencyType,
    Priority,
    SkillLevel,
    SkillStatus,
)
from roadmap.shared.ids import new_id


class Skill(BaseModel):
    """
    A learnable skill within the roadmap.

    Tracks both current state and target state, plus market/goal signals.
    """

    id: str = Field(default_factory=new_id)
    profile_id: str = Field(description="Owning profile ID")

    # Identity
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(
        default="general",
        max_length=100,
        description="High-level category, e.g. 'Programming', 'Mathematics'",
    )
    description: str = Field(default="", max_length=1000)

    # State
    current_level: SkillLevel = Field(default=SkillLevel.MISSING)
    target_level: SkillLevel = Field(default=SkillLevel.PROFICIENT)
    status: SkillStatus = Field(default=SkillStatus.PENDING)

    # Priority signals
    priority: Priority = Field(default=Priority.MEDIUM)
    market_demand_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How often this skill appears in job postings (0–1)",
    )
    goal_relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How directly this skill contributes to the goal (0–1)",
    )

    # Time
    estimated_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated hours to reach target_level from current_level",
    )

    # Prerequisites (names, resolved to IDs in graph layer)
    prerequisite_names: list[str] = Field(
        default_factory=list,
        description="Names of prerequisite skills",
    )

    # Evidence references (populated by research agent, MVP-3+)
    evidence_ids: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_completed(self) -> bool:
        return self.status == SkillStatus.COMPLETED

    @property
    def is_in_progress(self) -> bool:
        return self.status == SkillStatus.IN_PROGRESS

    @property
    def level_gap(self) -> int:
        """
        Number of levels between current and target.
        Returns 0 if current >= target.
        """
        gap = self.target_level.numeric() - self.current_level.numeric()
        return max(0, gap)

    @property
    def composite_priority_score(self) -> float:
        """
        Weighted combination of market demand and goal relevance.
        Used by PriorityCalculator as a starting signal.
        """
        return (self.market_demand_score * 0.4) + (self.goal_relevance_score * 0.6)

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)


class SkillDependency(BaseModel):
    """
    A directed prerequisite edge: from_skill must be learned before to_skill.

    Edge direction: from_skill_id → to_skill_id
    Meaning: to_skill DEPENDS ON from_skill.

    Example:
      C++ → OOP  (OOP requires C++ fundamentals)
    """

    id: str = Field(default_factory=new_id)
    from_skill_id: str = Field(description="Prerequisite skill ID")
    to_skill_id: str = Field(description="Dependent skill ID")
    dependency_type: DependencyType = Field(default=DependencyType.REQUIRES)
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence that this dependency is correct (0–1)",
    )
    source: str = Field(
        default="manual",
        description="Origin: 'manual', 'llm', 'curriculum', etc.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_hard_requirement(self) -> bool:
        return self.dependency_type == DependencyType.REQUIRES


