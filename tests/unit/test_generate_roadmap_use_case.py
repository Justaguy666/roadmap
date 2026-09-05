"""
Unit tests for GenerateRoadmapUseCase.

Tests deterministic skill gap computation, domain conversion,
and bounded retry on validation failure.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from roadmap.agents.schemas.roadmap_generation import (
    RoadmapGenerationResult,
    RoadmapPhaseDraft,
    RoadmapSkillDraft,
)
from roadmap.application.use_cases.generate_roadmap import GenerateRoadmapUseCase
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import RoadmapValidationError
from roadmap.domain.value_objects.enums import SkillLevel
from roadmap.infrastructure.llm.fake_provider import (
    FakeLLMProvider,
    get_default_fake_goal_analysis,
    get_default_fake_roadmap_result,
)
from roadmap.shared.ids import new_id


def make_profile() -> UserProfile:
    return UserProfile(
        id=new_id(),
        name="Charlie",
        target_goal="Become a Game Developer",
        target_role="Gameplay Programmer",
        current_level=SkillLevel.FAMILIAR,
        current_skills=["C++"],  # C++ is already familiar/known
        study_hours_per_day=2.0,
        deadline_months=12,
    )


class TestGenerateRoadmapUseCase:
    def test_compute_skill_gaps_deterministic(self) -> None:
        fake_llm = FakeLLMProvider()
        mock_profile_repo = MagicMock()
        mock_roadmap_repo = MagicMock()
        mock_skill_repo = MagicMock()

        uc = GenerateRoadmapUseCase(
            llm_provider=fake_llm,
            profile_repo=mock_profile_repo,
            roadmap_repo=mock_roadmap_repo,
            skill_repo=mock_skill_repo,
        )
        profile = make_profile()
        goal_analysis = get_default_fake_goal_analysis()

        gaps_result = uc._compute_skill_gaps(profile, goal_analysis)

        # C++ should be recognized as completed/no gap since Charlie has it in current_skills
        cpp_gap = next((g for g in gaps_result.gaps if g.skill == "C++"), None)
        assert cpp_gap is not None
        assert cpp_gap.gap == 0

        # Linear Algebra is not in current_skills, so it must have gap > 0
        math_gap = next((g for g in gaps_result.gaps if g.skill == "Linear Algebra"), None)
        assert math_gap is not None
        assert math_gap.gap > 0

    def test_successful_roadmap_generation_and_persistence(self) -> None:
        fake_llm = FakeLLMProvider()
        mock_profile_repo = MagicMock()
        mock_roadmap_repo = MagicMock()
        mock_skill_repo = MagicMock()

        uc = GenerateRoadmapUseCase(
            llm_provider=fake_llm,
            profile_repo=mock_profile_repo,
            roadmap_repo=mock_roadmap_repo,
            skill_repo=mock_skill_repo,
        )
        profile = make_profile()

        roadmap, goal_analysis, skill_gaps, val_result = uc.execute(profile)

        assert val_result.is_valid is True
        assert len(roadmap.phases) == 2
        assert roadmap.total_weeks == 14
        assert len(roadmap.all_skills) == 5

        # Verifies persistence was called
        mock_roadmap_repo.save.assert_called_once_with(roadmap)
        mock_skill_repo.save_skills.assert_called_once()
        mock_skill_repo.save_dependencies.assert_called_once()

    def test_retry_on_invalid_roadmap(self) -> None:
        """
        When the initial draft has a domain validation error (prerequisite order violation),
        the usecase should feed back errors and request a repair.
        """
        invalid_draft = RoadmapGenerationResult(
            roadmap_objective="Comprehensive Learning Objective",
            phases=[
                RoadmapPhaseDraft(
                    phase_name="Phase 1",
                    objective="Basics",
                    estimated_duration_weeks=4.0,
                    skills=[
                        RoadmapSkillDraft(
                            name="C++",
                            prerequisites=["Advanced Physics"],  # Prerequisite in later phase!
                        )
                    ],
                ),
                RoadmapPhaseDraft(
                    phase_name="Phase 2",
                    objective="Advanced",
                    estimated_duration_weeks=4.0,
                    skills=[
                        RoadmapSkillDraft(
                            name="Advanced Physics",
                            prerequisites=[],
                        )
                    ],
                ),
            ],
        )

        valid_draft = get_default_fake_roadmap_result()

        fake_llm = FakeLLMProvider()
        responses = [invalid_draft, valid_draft]

        def mock_complete(*args, **kwargs):
            if kwargs.get("response_model").__name__ == "GoalAnalysisResult":
                return get_default_fake_goal_analysis()
            return responses.pop(0)

        fake_llm.complete = mock_complete  # type: ignore[assignment]

        uc = GenerateRoadmapUseCase(
            llm_provider=fake_llm,
            profile_repo=MagicMock(),
            roadmap_repo=MagicMock(),
            skill_repo=MagicMock(),
            max_retries=3,
        )
        profile = make_profile()

        roadmap, _, __, val_result = uc.execute(profile)
        assert val_result.is_valid is True
        assert len(roadmap.phases) == 2

    def test_exhausted_retries_raises_validation_error(self) -> None:
        """
        If all retries produce an invalid roadmap, RoadmapValidationError is raised.
        """
        invalid_draft = RoadmapGenerationResult(
            roadmap_objective="Comprehensive Learning Objective",
            phases=[
                RoadmapPhaseDraft(
                    phase_name="Phase 1",
                    objective="Basics",
                    estimated_duration_weeks=4.0,
                    skills=[
                        RoadmapSkillDraft(
                            name="C++",
                            prerequisites=["Advanced Physics"],  # Prerequisite in later phase!
                        )
                    ],
                ),
                RoadmapPhaseDraft(
                    phase_name="Phase 2",
                    objective="Advanced",
                    estimated_duration_weeks=4.0,
                    skills=[
                        RoadmapSkillDraft(
                            name="Advanced Physics",
                            prerequisites=[],
                        )
                    ],
                ),
            ],
        )

        fake_llm = FakeLLMProvider()

        def mock_complete(*args, **kwargs):
            if kwargs.get("response_model").__name__ == "GoalAnalysisResult":
                return get_default_fake_goal_analysis()
            return invalid_draft

        fake_llm.complete = mock_complete  # type: ignore[assignment]

        uc = GenerateRoadmapUseCase(
            llm_provider=fake_llm,
            profile_repo=MagicMock(),
            roadmap_repo=MagicMock(),
            skill_repo=MagicMock(),
            max_retries=2,
        )
        profile = make_profile()

        with pytest.raises(RoadmapValidationError) as exc_info:
            uc.execute(profile)
        assert "Advanced Physics" in str(exc_info.value) or "requires" in str(exc_info.value)
