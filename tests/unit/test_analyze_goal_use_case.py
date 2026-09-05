"""
Unit tests for AnalyzeGoalUseCase.

Verifies prompt building, LLMProvider delegation, and domain Goal entity conversion.
"""

from __future__ import annotations

from roadmap.application.use_cases.analyze_goal import AnalyzeGoalUseCase
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects.enums import SkillLevel
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.shared.ids import new_id


def make_profile() -> UserProfile:
    return UserProfile(
        id=new_id(),
        name="Bob",
        target_goal="Become a Game Developer",
        target_role="Gameplay Programmer",
        current_level=SkillLevel.FAMILIAR,
        current_skills=["C++", "Python"],
        study_hours_per_day=2.0,
        deadline_months=6,
    )


class TestAnalyzeGoalUseCase:
    def test_analyze_goal_executes_successfully(self) -> None:
        fake_llm = FakeLLMProvider()
        uc = AnalyzeGoalUseCase(llm_provider=fake_llm)
        profile = make_profile()

        result = uc.execute(profile)
        assert result.target_role == "Gameplay Programmer"
        assert len(result.competencies) == 3
        assert len(result.required_skills) == 5
        assert len(fake_llm.calls) == 1
        assert fake_llm.calls[0]["response_model"] == "GoalAnalysisResult"

    def test_convert_to_domain_goal(self) -> None:
        fake_llm = FakeLLMProvider()
        uc = AnalyzeGoalUseCase(llm_provider=fake_llm)
        profile = make_profile()

        analysis = uc.execute(profile)
        domain_goal = uc.to_domain_goal(profile, analysis)

        assert domain_goal.profile_id == profile.id
        assert domain_goal.target_role == "Gameplay Programmer"
        assert domain_goal.is_analyzed is True
        assert len(domain_goal.competencies) == len(analysis.competencies)
        assert len(domain_goal.required_skill_names) == len(analysis.required_skills)
