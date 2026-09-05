"""Domain entities: LearningResource and Project."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from roadmap.domain.value_objects import ResourceType, SkillLevel
from roadmap.shared.ids import new_id


class LearningResource(BaseModel):
    """
    A curated learning resource (book, course, video, etc.) for a skill.

    Resources are evaluated for quality, freshness, cost, and difficulty.
    """

    id: str = Field(default_factory=new_id)
    phase_id: str = Field(default="", description="Roadmap phase this belongs to")

    # Identity
    title: str = Field(min_length=1, max_length=300)
    resource_type: ResourceType = Field(default=ResourceType.COURSE)
    url: str = Field(default="", max_length=2000)
    provider: str = Field(
        default="",
        max_length=200,
        description="Platform or publisher, e.g. 'Coursera', 'O'Reilly'",
    )

    # Assessment
    difficulty: SkillLevel = Field(default=SkillLevel.FAMILIAR)
    estimated_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated hours to complete",
    )
    cost: float = Field(default=0.0, ge=0.0, description="Cost in USD")
    is_free: bool = Field(default=True)
    freshness_year: int = Field(
        default=2024,
        description="Year of last significant update",
    )
    quality_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Curated quality assessment (0–1)",
    )

    # Associations
    associated_skill_names: list[str] = Field(
        default_factory=list,
        description="Skills this resource covers",
    )
    source_id: str = Field(
        default="",
        description="Evidence source ID if resource was found by research agent",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_affordable(self) -> bool:
        return self.is_free or self.cost == 0.0

    def affordable_for(self, budget_usd: float) -> bool:
        return self.is_free or self.cost <= budget_usd


class Project(BaseModel):
    """
    A practical project to reinforce skills and build portfolio value.

    Projects are assigned to roadmap phases and should be completable
    within the phase's estimated duration.
    """

    id: str = Field(default_factory=new_id)
    phase_id: str = Field(default="", description="Roadmap phase this belongs to")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    required_skill_names: list[str] = Field(
        default_factory=list,
        description="Skills needed to complete this project",
    )
    difficulty: SkillLevel = Field(default=SkillLevel.FAMILIAR)
    expected_outcome: str = Field(
        default="",
        max_length=500,
        description="What the user will have built or demonstrated",
    )
    portfolio_value: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How valuable this project is for a portfolio (0–1)",
    )
    estimated_hours: float = Field(default=20.0, ge=0.0)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_high_value(self) -> bool:
        return self.portfolio_value >= 0.7

