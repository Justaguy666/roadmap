"""
Structured LLM schemas for Goal Analysis.

These schemas define the exact contract expected from the LLM
when analyzing a user's goal and inferring the competency model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from roadmap.domain.value_objects.enums import Priority, SkillLevel


class CompetencyDraft(BaseModel):
    """A high-level capability area inferred by the LLM."""

    name: str = Field(min_length=1, max_length=150, description="Competency area name, e.g. 'Game Programming'")
    category: str = Field(default="general", max_length=100, description="General domain category")
    importance_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Relative importance to the goal (0.0 to 1.0)",
    )
    description: str = Field(default="", max_length=500, description="Brief explanation of this competency")
    skill_names: list[str] = Field(
        default_factory=list,
        description="Names of specific skills that comprise this competency",
    )


class RequiredSkillDraft(BaseModel):
    """A core skill deemed strictly necessary for the target role/goal."""

    name: str = Field(min_length=1, max_length=150, description="Skill name, e.g. 'C++'")
    category: str = Field(default="general", max_length=100, description="Category, e.g. 'programming', 'math'")
    target_level: SkillLevel = Field(
        default=SkillLevel.PROFICIENT,
        description="Target mastery level required for this role",
    )
    priority: Priority = Field(
        default=Priority.HIGH,
        description="Urgency/importance priority",
    )
    description: str = Field(default="", max_length=500, description="What this skill entails")
    rationale: str = Field(default="", max_length=500, description="Why this skill is mandatory for the goal")


class OptionalSkillDraft(BaseModel):
    """A complementary or stretch skill that enhances the candidate's profile."""

    name: str = Field(min_length=1, max_length=150, description="Skill name")
    category: str = Field(default="general", max_length=100, description="Category")
    rationale: str = Field(default="", max_length=500, description="Why this skill is beneficial but not blocker")


class GoalAnalysisResult(BaseModel):
    """Structured LLM output for the Goal Analysis step."""

    interpreted_goal: str = Field(
        min_length=5,
        max_length=500,
        description="The LLM's structured understanding of the user's ultimate goal",
    )
    target_role: str = Field(
        min_length=2,
        max_length=150,
        description="Standardized career role title, e.g. 'Gameplay Programmer'",
    )
    competencies: list[CompetencyDraft] = Field(
        default_factory=list,
        min_length=1,
        description="High-level competency areas required",
    )
    required_skills: list[RequiredSkillDraft] = Field(
        default_factory=list,
        min_length=1,
        description="Non-negotiable core skills required for the role",
    )
    optional_skills: list[OptionalSkillDraft] = Field(
        default_factory=list,
        description="Optional or secondary skills that are nice-to-have",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions made by the LLM regarding user baseline, industry standards, or specialization",
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score in this goal analysis (0.0 to 1.0)",
    )
