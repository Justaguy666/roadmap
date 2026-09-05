"""Agents structured Pydantic schemas."""

from roadmap.agents.schemas.evaluator import (
    EvaluationIssue,
    RoadmapEvaluationResult,
)
from roadmap.agents.schemas.goal_analysis import (
    CompetencyDraft,
    GoalAnalysisResult,
    OptionalSkillDraft,
    RequiredSkillDraft,
)
from roadmap.agents.schemas.research import (
    EvidenceExtractionResult,
    ExtractedClaimDraft,
    MarketResearchResult,
    MarketSkillObservation,
    RecommendedResourceDraft,
    ResearchPlan,
    ResearchQuery,
    ResourceResearchResult,
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
    "EvaluationIssue",
    "EvidenceExtractionResult",
    "ExtractedClaimDraft",
    "GoalAnalysisResult",
    "MarketResearchResult",
    "MarketSkillObservation",
    "OptionalSkillDraft",
    "RecommendedResourceDraft",
    "RequiredSkillDraft",
    "ResearchPlan",
    "ResearchQuery",
    "ResourceResearchResult",
    "RoadmapEvaluationResult",
    "RoadmapGenerationResult",
    "RoadmapMilestoneDraft",
    "RoadmapPhaseDraft",
    "RoadmapProjectDraft",
    "RoadmapResourceDraft",
    "RoadmapSkillDraft",
    "SkillGapAnalysisResult",
    "SkillGapItem",
]
