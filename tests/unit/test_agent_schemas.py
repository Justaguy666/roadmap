"""
Unit tests for MVP-2 Agent Pydantic Schemas.

Validates schema constraints, boundaries, and type validations.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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
    RoadmapSkillDraft,
)
from roadmap.agents.schemas.skill_gap import SkillGapItem
from roadmap.domain.value_objects.enums import Priority, SkillLevel


class TestGoalAnalysisSchemas:
    def test_valid_goal_analysis_result(self) -> None:
        result = GoalAnalysisResult(
            interpreted_goal="Master C++ and build game engines",
            target_role="Engine Programmer",
            competencies=[
                CompetencyDraft(
                    name="Systems",
                    category="programming",
                    importance_score=0.9,
                    description="Systems programming",
                    skill_names=["C++", "Memory Management"],
                )
            ],
            required_skills=[
                RequiredSkillDraft(
                    name="C++",
                    category="programming",
                    target_level=SkillLevel.PROFICIENT,
                    priority=Priority.CRITICAL,
                    description="C++ language mastery",
                    rationale="Industry standard",
                )
            ],
            optional_skills=[
                OptionalSkillDraft(name="Vulkan", category="graphics", rationale="Bonus")
            ],
            assumptions=["Junior candidate baseline"],
            confidence=0.95,
        )
        assert result.target_role == "Engine Programmer"
        assert result.confidence == 0.95
        assert len(result.competencies) == 1
        assert len(result.required_skills) == 1

    def test_confidence_range_validation(self) -> None:
        with pytest.raises(ValidationError):
            GoalAnalysisResult(
                interpreted_goal="Valid goal statement",
                target_role="Role",
                competencies=[CompetencyDraft(name="C1")],
                required_skills=[RequiredSkillDraft(name="S1")],
                confidence=1.5,  # Invalid: > 1.0
            )

        with pytest.raises(ValidationError):
            GoalAnalysisResult(
                interpreted_goal="Valid goal statement",
                target_role="Role",
                competencies=[CompetencyDraft(name="C1")],
                required_skills=[RequiredSkillDraft(name="S1")],
                confidence=-0.1,  # Invalid: < 0.0
            )

    def test_empty_required_skills_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GoalAnalysisResult(
                interpreted_goal="Valid goal statement",
                target_role="Role",
                competencies=[CompetencyDraft(name="C1")],
                required_skills=[],  # Invalid: min_length=1
            )


class TestSkillGapSchemas:
    def test_skill_gap_item_validation(self) -> None:
        item = SkillGapItem(
            skill="C++",
            current_level=SkillLevel.MISSING,
            target_level=SkillLevel.PROFICIENT,
            gap=3,
            priority=Priority.CRITICAL,
            reasoning="Needs 3 levels of advancement",
        )
        assert item.gap == 3
        assert item.priority == Priority.CRITICAL

    def test_skill_gap_bounds(self) -> None:
        with pytest.raises(ValidationError):
            SkillGapItem(
                skill="C++",
                current_level=SkillLevel.MISSING,
                target_level=SkillLevel.PROFICIENT,
                gap=5,  # Invalid: > 4
                priority=Priority.CRITICAL,
            )


class TestRoadmapGenerationSchemas:
    def test_valid_roadmap_generation_result(self) -> None:
        result = RoadmapGenerationResult(
            roadmap_objective="Full path to Gameplay Engineer",
            phases=[
                RoadmapPhaseDraft(
                    phase_name="Phase 1: Foundations",
                    objective="Learn C++ basics",
                    estimated_duration_weeks=4.0,
                    priority=Priority.HIGH,
                    skills=[
                        RoadmapSkillDraft(
                            name="C++",
                            target_level=SkillLevel.PROFICIENT,
                            priority=Priority.CRITICAL,
                            estimated_hours=40.0,
                        )
                    ],
                    projects=[
                        RoadmapProjectDraft(
                            title="Text Adventure Game",
                            description="Build terminal game in C++",
                            skills_practiced=["C++"],
                            difficulty=SkillLevel.FAMILIAR,
                            expected_outcome="Playable terminal game",
                            portfolio_value=0.5,
                            estimated_hours=15.0,
                        )
                    ],
                    milestones=[
                        RoadmapMilestoneDraft(
                            measurable_outcome="Can compile C++ with no warnings",
                            exit_criteria=["Builds with -Wall -Wextra -Werror"],
                            estimated_weeks=1.0,
                        )
                    ],
                )
            ],
            assumptions=["15 hours per week"],
            total_estimated_weeks=4.0,
        )
        assert len(result.phases) == 1
        assert result.phases[0].skills[0].name == "C++"

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RoadmapPhaseDraft(
                phase_name="Invalid Phase",
                objective="Objective",
                estimated_duration_weeks=0.0,  # Invalid: gt=0.0
                skills=[RoadmapSkillDraft(name="Skill")],
            )

    def test_empty_exit_criteria_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RoadmapMilestoneDraft(
                measurable_outcome="Outcome",
                exit_criteria=[],  # Invalid: min_length=1
            )
