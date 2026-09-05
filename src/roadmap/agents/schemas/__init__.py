"""Agents structured Pydantic schemas."""

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
from roadmap.agents.schemas.skill_gap import (
    SkillGapAnalysisResult,
    SkillGapItem,
)

__all__ = [
    "CompetencyDraft",
    "GoalAnalysisResult",
    "OptionalSkillDraft",
    "RequiredSkillDraft",
    "RoadmapGenerationResult",
    "RoadmapMilestoneDraft",
    "RoadmapPhaseDraft",
    "RoadmapProjectDraft",
    "RoadmapResourceDraft",
    "RoadmapSkillDraft",
    "SkillGapAnalysisResult",
    "SkillGapItem",
]
