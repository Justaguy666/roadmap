"""Unit tests for PriorityCalculator domain service."""

from __future__ import annotations

import pytest

from roadmap.domain.entities.skill import Skill
from roadmap.domain.services.priority_calculator import (
    DEFAULT_WEIGHTS,
    PriorityCalculator,
    PriorityWeights,
)
from roadmap.domain.value_objects import Priority, SkillLevel
from roadmap.shared.ids import new_id


def make_skill(
    market_demand: float = 0.5,
    goal_relevance: float = 0.5,
    current: SkillLevel = SkillLevel.MISSING,
    target: SkillLevel = SkillLevel.PROFICIENT,
    name: str = "TestSkill",
) -> Skill:
    return Skill(
        id=new_id(),
        profile_id="p1",
        name=name,
        current_level=current,
        target_level=target,
        market_demand_score=market_demand,
        goal_relevance_score=goal_relevance,
    )


class TestPriorityCalculator:
    def setup_method(self) -> None:
        self.calc = PriorityCalculator()

    def test_default_weights_sum_to_one(self) -> None:
        assert DEFAULT_WEIGHTS.validate()

    def test_high_demand_high_relevance_gives_high_score(self) -> None:
        skill = make_skill(market_demand=1.0, goal_relevance=1.0)
        score = self.calc.compute_score(skill)
        assert score > 0.6

    def test_zero_demand_zero_relevance_gives_low_score(self) -> None:
        skill = make_skill(
            market_demand=0.0,
            goal_relevance=0.0,
            current=SkillLevel.MASTERED,
            target=SkillLevel.MASTERED,  # no gap
        )
        score = self.calc.compute_score(skill)
        # time factor is small but not zero
        assert score < 0.1

    def test_score_in_range(self) -> None:
        skill = make_skill(market_demand=0.7, goal_relevance=0.8)
        score = self.calc.compute_score(skill)
        assert 0.0 <= score <= 1.0

    def test_many_dependents_boosts_score(self) -> None:
        skill_no_deps = make_skill(market_demand=0.5, goal_relevance=0.5, name="A")
        skill_many_deps = make_skill(market_demand=0.5, goal_relevance=0.5, name="B")
        score_no = self.calc.compute_score(skill_no_deps, dependent_count=0)
        score_many = self.calc.compute_score(skill_many_deps, dependent_count=10)
        assert score_many > score_no

    def test_assign_priority_critical(self) -> None:
        skill = make_skill(market_demand=1.0, goal_relevance=1.0)
        priority = self.calc.assign_priority(skill, dependent_count=8)
        assert priority == Priority.CRITICAL

    def test_assign_priority_low(self) -> None:
        skill = make_skill(
            market_demand=0.0,
            goal_relevance=0.0,
            current=SkillLevel.MASTERED,
            target=SkillLevel.MASTERED,
        )
        priority = self.calc.assign_priority(skill)
        assert priority == Priority.LOW

    def test_rank_skills_sorted_descending(self) -> None:
        skills = [
            make_skill(0.1, 0.1, name="Low"),
            make_skill(0.9, 0.9, name="High"),
            make_skill(0.5, 0.5, name="Mid"),
        ]
        ranked = self.calc.rank_skills(skills)
        names = [s.name for s, _ in ranked]
        assert names[0] == "High"
        assert names[-1] == "Low"

    def test_custom_weights(self) -> None:
        # Give all weight to market demand
        weights = PriorityWeights(
            market_demand=0.96,
            goal_relevance=0.01,
            level_gap_urgency=0.01,
            prerequisite_pressure=0.01,
            time_factor=0.01,
        )
        calc = PriorityCalculator(weights)
        high_market = make_skill(market_demand=1.0, goal_relevance=0.0, name="HM")
        low_market = make_skill(market_demand=0.0, goal_relevance=1.0, name="LM")
        assert calc.compute_score(high_market) > calc.compute_score(low_market)
