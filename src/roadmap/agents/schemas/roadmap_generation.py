"""
Structured LLM schemas for Roadmap Generation.

Defines the exact schema expected from the LLM when producing
a full, structured learning roadmap draft.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from roadmap.domain.value_objects.enums import Priority, ResourceType, SkillLevel


class RoadmapSkillDraft(BaseModel):
    """A skill embedded within a specific roadmap phase."""

    name: str = Field(min_length=1, max_length=150, description="Skill name")
    category: str = Field(default="general", max_length=100)
    target_level: SkillLevel = Field(
        default=SkillLevel.PROFICIENT,
        description="Target proficiency achieved in this phase",
    )
    priority: Priority = Field(
        default=Priority.HIGH,
        description="Priority of mastering this skill within the phase",
    )
    prerequisites: list[str] = Field(
        default_factory=list,
        description="Names of direct prerequisite skills that must be learned beforehand",
    )
    estimated_hours: float = Field(
        default=20.0,
        ge=0.0,
        le=1000.0,
        description="Estimated learning hours required for this skill",
    )


class RoadmapProjectDraft(BaseModel):
    """A milestone portfolio project anchoring a phase."""

    title: str = Field(min_length=1, max_length=200, description="Project title")
    description: str = Field(min_length=5, max_length=1500, description="Clear description of the project")
    skills_practiced: list[str] = Field(
        default_factory=list,
        min_length=1,
        description="Skills reinforced through building this project",
    )
    difficulty: SkillLevel = Field(
        default=SkillLevel.FAMILIAR,
        description="Expected implementation difficulty level",
    )
    expected_outcome: str = Field(
        default="",
        max_length=500,
        description="Observable deliverable, e.g. 'A playable 2D platformer with custom collision physics'",
    )
    portfolio_value: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Portfolio impact value (0.0 to 1.0)",
    )
    estimated_hours: float = Field(
        default=20.0,
        ge=0.0,
        le=500.0,
        description="Estimated hours to complete the project",
    )


class RoadmapMilestoneDraft(BaseModel):
    """A verifiable checkpoint marking the exit of a phase."""

    measurable_outcome: str = Field(
        min_length=3,
        max_length=300,
        description="Clear statement of what milestone was reached",
    )
    exit_criteria: list[str] = Field(
        min_length=1,
        description="List of verifiable criteria that must be satisfied before moving to next phase",
    )
    estimated_weeks: float = Field(
        default=1.0,
        ge=0.0,
        le=52.0,
        description="Estimated duration dedicated to milestone validation",
    )


class RoadmapResourceDraft(BaseModel):
    """Recommended learning resource placeholder or starter."""

    title: str = Field(min_length=1, max_length=250)
    resource_type: ResourceType = Field(default=ResourceType.COURSE)
    url: str = Field(default="", max_length=1000)
    provider: str = Field(default="", max_length=150)
    difficulty: SkillLevel = Field(default=SkillLevel.FAMILIAR)
    estimated_hours: float = Field(default=10.0, ge=0.0)


class RoadmapPhaseDraft(BaseModel):
    """A sequential phase in the learning path."""

    phase_name: str = Field(min_length=2, max_length=150, description="Title of the phase")
    objective: str = Field(
        min_length=5,
        max_length=500,
        description="Primary learning objective and capabilities gained",
    )
    estimated_duration_weeks: float = Field(
        default=4.0,
        gt=0.0,
        le=104.0,
        description="Estimated duration in weeks",
    )
    priority: Priority = Field(default=Priority.MEDIUM)
    skills: list[RoadmapSkillDraft] = Field(
        min_length=1,
        description="Skills scheduled for learning during this phase",
    )
    projects: list[RoadmapProjectDraft] = Field(
        default_factory=list,
        description="Hands-on projects for this phase",
    )
    milestones: list[RoadmapMilestoneDraft] = Field(
        default_factory=list,
        description="Verification milestones for phase exit",
    )
    resources: list[RoadmapResourceDraft] = Field(
        default_factory=list,
        description="Curated resources for this phase",
    )


class RoadmapGenerationResult(BaseModel):
    """Complete structured output from the LLM for roadmap generation."""

    roadmap_objective: str = Field(
        min_length=5,
        max_length=500,
        description="Overall objective and target state of the roadmap",
    )
    phases: list[RoadmapPhaseDraft] = Field(
        min_length=1,
        description="Chronologically ordered phases from foundational to advanced",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Underlying assumptions about pace, prerequisites, or industry focus",
    )
    total_estimated_weeks: float = Field(
        default=0.0,
        ge=0.0,
        description="Calculated or estimated total weeks",
    )
