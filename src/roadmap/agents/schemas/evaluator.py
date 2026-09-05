"""Pydantic schemas for the RoadmapEvaluator agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvaluationIssue(BaseModel):
    category: Literal[
        "structural",
        "goal_alignment",
        "market_alignment",
        "time_feasibility",
        "evidence_alignment",
        "educational_coherence",
        "scope",
    ]
    severity: Literal["critical", "major", "minor"]
    message: str
    affected_item: str = Field(default="", description="Phase, skill, or project name affected")


class RoadmapEvaluationResult(BaseModel):
    """Structured evaluation output returned by RoadmapEvaluator."""

    verdict: Literal["PASS", "REVISE"]
    score: float = Field(ge=0.0, le=100.0, description="Evaluator assessed score out of 100")
    issues: list[EvaluationIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list, description="Crucial market/goal skills omitted")
    prerequisite_violations: list[str] = Field(default_factory=list, description="Sequencing issues identified")
    evidence_violations: list[str] = Field(default_factory=list, description="Unsubstantiated market claims")
    time_violations: list[str] = Field(default_factory=list, description="Excessive workload or impossible deadlines")
    recommendations: list[str] = Field(default_factory=list, description="Concrete, actionable fixes for planner")
