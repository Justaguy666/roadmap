"""
Domain service: PriorityCalculator.

Computes a skill's priority using a weighted combination of signals:
  - Market demand score (from research agent)
  - Goal relevance score
  - Skill level gap (bigger gap → higher urgency for foundational skills)
  - Prerequisite status (skills with many dependents get a boost)
  - Time constraint factor

All inputs are domain values — no LLM calls, no external deps.
"""

from __future__ import annotations

from dataclasses import dataclass

from roadmap.domain.entities.skill import Skill
from roadmap.domain.value_objects import Priority


@dataclass(frozen=True)
class PriorityWeights:
    """
    Configurable weights for the priority calculation formula.

    All weights should sum to 1.0 for a normalized score.
    """

    market_demand: float = 0.30
    goal_relevance: float = 0.35
    level_gap_urgency: float = 0.20   # higher gap → more urgent
    prerequisite_pressure: float = 0.10  # how many skills depend on this
    time_factor: float = 0.05          # deadline closeness

    def validate(self) -> bool:
        total = (
            self.market_demand
            + self.goal_relevance
            + self.level_gap_urgency
            + self.prerequisite_pressure
            + self.time_factor
        )
        return abs(total - 1.0) < 0.001


DEFAULT_WEIGHTS = PriorityWeights()


class PriorityCalculator:
    """
    Computes priority scores for skills.

    Priority is NOT simply "most popular skill wins."
    It balances market demand, goal fit, learning urgency, and dependencies.
    """

    def __init__(self, weights: PriorityWeights = DEFAULT_WEIGHTS) -> None:
        self._weights = weights

    def compute_score(
        self,
        skill: Skill,
        dependent_count: int = 0,      # how many skills depend on this one
        deadline_months_remaining: int = 12,
    ) -> float:
        """
        Compute a normalized priority score in [0, 1].

        Args:
            skill: The skill to score.
            dependent_count: Number of skills that have this skill as a prerequisite.
            deadline_months_remaining: How many months until the user's deadline.

        Returns:
            float in [0.0, 1.0] — higher is more urgent.
        """
        w = self._weights

        # Market demand: 0–1 from research
        market_score = skill.market_demand_score

        # Goal relevance: 0–1 from goal analysis
        relevance_score = skill.goal_relevance_score

        # Level gap urgency: normalized gap (0–4 levels → 0–1)
        gap = skill.level_gap
        gap_score = gap / 4.0

        # Prerequisite pressure: skills with many dependents should come first
        # Normalize against a reasonable max (10 dependents → 1.0)
        dep_score = min(dependent_count / 10.0, 1.0)

        # Time factor: closer deadlines → everything is more urgent
        # 1 month = 1.0, 12 months = 0.08, 24+ months = ~0
        time_score = min(1.0, 1.0 / max(deadline_months_remaining, 1))

        score = (
            w.market_demand * market_score
            + w.goal_relevance * relevance_score
            + w.level_gap_urgency * gap_score
            + w.prerequisite_pressure * dep_score
            + w.time_factor * time_score
        )

        return round(min(1.0, max(0.0, score)), 4)

    def assign_priority(
        self,
        skill: Skill,
        dependent_count: int = 0,
        deadline_months_remaining: int = 12,
    ) -> Priority:
        """
        Assign a discrete Priority from the computed score.

        Thresholds:
          CRITICAL: score >= 0.75
          HIGH:     score >= 0.50
          MEDIUM:   score >= 0.25
          LOW:      score < 0.25
        """
        score = self.compute_score(skill, dependent_count, deadline_months_remaining)
        if score >= 0.75:
            return Priority.CRITICAL
        if score >= 0.50:
            return Priority.HIGH
        if score >= 0.25:
            return Priority.MEDIUM
        return Priority.LOW

    def rank_skills(
        self,
        skills: list[Skill],
        dependent_counts: dict[str, int] | None = None,
        deadline_months_remaining: int = 12,
    ) -> list[tuple[Skill, float]]:
        """
        Return skills sorted by priority score descending.

        Returns list of (skill, score) tuples.
        """
        if dependent_counts is None:
            dependent_counts = {}

        scored = [
            (skill, self.compute_score(
                skill,
                dependent_counts.get(skill.id, 0),
                deadline_months_remaining,
            ))
            for skill in skills
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
