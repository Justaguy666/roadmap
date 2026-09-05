"""Domain service: RoadmapDecisionService.

Evaluates deterministic inclusion, postponement, and priority decisions for skills
based on composite scoring:
- Market relevance (from MarketIntelligenceService)
- Goal relevance
- Skill gap (missing -> proficient)
- Prerequisite importance (number of dependents)
- Portfolio value
- Time cost factor
"""

from __future__ import annotations

from roadmap.domain.entities.evidence_aggregation import (
    MarketObservation,
    SkillDecision,
    SkillDecisionFactors,
    SkillEvidenceSummary,
)
from roadmap.domain.entities.skill import Skill
from roadmap.domain.value_objects import Priority


class RoadmapDecisionService:
    """Computes transparent, evidence-backed skill inclusion and priority decisions."""

    @staticmethod
    def evaluate_skill(
        skill: Skill,
        evidence_summary: SkillEvidenceSummary | None = None,
        market_obs: MarketObservation | None = None,
        dependent_count: int = 0,
        estimated_hours: float = 25.0,
    ) -> SkillDecision:
        """Compute structured SkillDecision with explicit factor weights."""
        # 1. Market relevance
        if market_obs and not market_obs.insufficient_sample:
            market_rel = market_obs.observed_frequency
        elif evidence_summary and evidence_summary.evidence_count > 0:
            market_rel = evidence_summary.weighted_score
        else:
            market_rel = 0.35

        # 2. Goal relevance
        goal_rel = skill.goal_relevance_score if skill.goal_relevance_score > 0 else 0.70

        # 3. Skill gap factor (normalized 0..1)
        # Gap between current and target
        gap = max(0, skill.target_level.numeric() - skill.current_level.numeric())
        skill_gap_factor = min(1.0, gap / 3.0)

        # 4. Prerequisite importance
        prereq_importance = min(1.0, dependent_count * 0.25)

        # 5. Portfolio value (heuristic based on category and target level)
        is_applied = any(cat in skill.category.lower() for cat in ("game", "graphics", "backend", "fullstack", "project", "engine"))
        portfolio_val = 0.85 if is_applied else 0.60

        # 6. Time cost factor (lower hours -> higher factor, less friction)
        time_factor = max(0.2, min(1.0, 1.0 - (estimated_hours / 120.0)))

        factors = SkillDecisionFactors(
            market_relevance=round(market_rel, 3),
            goal_relevance=round(goal_rel, 3),
            skill_gap=round(skill_gap_factor, 3),
            prerequisite_importance=round(prereq_importance, 3),
            portfolio_value=round(portfolio_val, 3),
            time_cost_factor=round(time_factor, 3),
        )

        # Deterministic composite score formula:
        # Market(0.25) + Goal(0.30) + Gap(0.20) + Prereq(0.15) + Portfolio(0.10)
        composite = (
            (factors.market_relevance * 0.25)
            + (factors.goal_relevance * 0.30)
            + (factors.skill_gap * 0.20)
            + (factors.prerequisite_importance * 0.15)
            + (factors.portfolio_value * 0.10)
        )
        composite = round(min(1.0, max(0.0, composite)), 3)

        # Decide action and priority
        if composite >= 0.70:
            decision = "include"
            priority = Priority.CRITICAL if composite >= 0.85 else Priority.HIGH
            decision_msg = f"Strong market signal ({int(market_rel*100)}%) and high goal alignment."
        elif composite >= 0.45:
            decision = "include"
            priority = Priority.MEDIUM
            decision_msg = "Balanced prerequisite and core competency value."
        else:
            decision = "postpone"
            priority = Priority.LOW
            decision_msg = "Lower immediate priority or secondary elective specialization."

        evidence_ids = evidence_summary.supporting_evidence_ids if evidence_summary else []
        conf = evidence_summary.average_confidence if (evidence_summary and evidence_summary.evidence_count > 0) else 0.70

        return SkillDecision(
            skill_name=skill.name,
            decision=decision,
            priority=priority,
            composite_score=composite,
            factors=factors,
            evidence_ids=evidence_ids,
            confidence=round(conf, 3),
            supporting_evidence_count=len(evidence_ids),
            contradicting_evidence_count=len(evidence_summary.contradicting_evidence_ids) if evidence_summary else 0,
            rationale=decision_msg,
        )
