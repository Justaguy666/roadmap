"""Unit tests for RoadmapEvaluator agent."""

from __future__ import annotations

from roadmap.agents.evaluator import RoadmapEvaluator
from roadmap.agents.schemas.evaluator import EvaluationIssue, RoadmapEvaluationResult
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider


def test_evaluator_agent_pass_verdict() -> None:
    fake_llm = FakeLLMProvider()
    evaluator = RoadmapEvaluator(fake_llm)

    res = evaluator.evaluate(
        target_role="Gameplay Programmer",
        target_goal="Become a professional game developer",
        weekly_hours=15.0,
        deadline_weeks=24.0,
        candidate_roadmap_dict={"phases": []},
        market_summary_list=[],
    )

    assert res.verdict == "PASS"
    assert res.score >= 80.0
    assert len(res.issues) == 0


def test_evaluator_deterministic_errors_critique() -> None:
    fake_llm = FakeLLMProvider()

    def mock_complete(*args, **kwargs):
        return RoadmapEvaluationResult(
            verdict="REVISE",
            score=45.0,
            issues=[
                EvaluationIssue(
                    category="structural",
                    severity="critical",
                    message="Prerequisite cycle detected: C++ <-> OOP",
                )
            ],
            recommendations=["Break circular dependency between C++ and OOP."],
        )

    fake_llm.complete = mock_complete  # type: ignore[assignment]
    evaluator = RoadmapEvaluator(fake_llm)

    res = evaluator.evaluate(
        target_role="Gameplay Programmer",
        target_goal="Become a professional game developer",
        weekly_hours=15.0,
        deadline_weeks=24.0,
        candidate_roadmap_dict={"phases": []},
        market_summary_list=[],
        deterministic_errors=["Circular dependency in skill graph"],
    )

    assert res.verdict == "REVISE"
    assert res.score < 50.0
    assert len(res.issues) == 1
    assert "circular" in res.recommendations[0].lower()
