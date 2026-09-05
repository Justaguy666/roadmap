"""Domain service: QualityScorer.

Computes a multi-dimensional quality assessment for a roadmap on a 0-100 scale:
1. Goal Alignment (weight 0.20)
2. Market Alignment (weight 0.20)
3. Evidence Strength (weight 0.15)
4. Dependency Correctness (weight 0.15)
5. Time Feasibility (weight 0.15)
6. Portfolio Value (weight 0.10)
7. Scope Efficiency (weight 0.05)
"""

from __future__ import annotations

from roadmap.domain.entities.evidence_aggregation import RoadmapQualityScore, SkillEvidenceSummary
from roadmap.domain.entities.roadmap import Roadmap
from roadmap.domain.entities.user_profile import UserProfile


class QualityScorer:
    """Calculates deterministic quality dimensions for roadmaps."""

    @staticmethod
    def calculate_score(
        roadmap: Roadmap,
        profile: UserProfile,
        evidence_summaries: dict[str, SkillEvidenceSummary] | None = None,
        has_cycles: bool = False,
    ) -> RoadmapQualityScore:
        """Evaluate roadmap quality across 7 dimensions."""
        notes: list[str] = []

        # 1. Dependency correctness
        dep_score = 100.0
        if has_cycles:
            dep_score = 0.0
            notes.append("Dependency cycles detected in curriculum graph.")

        # Check phase prerequisite ordering
        phase_order: dict[str, int] = {}
        for p_idx, phase in enumerate(roadmap.phases):
            for sk in phase.skills:
                phase_order[sk.name.lower()] = p_idx

        ordering_violations = 0
        for p_idx, phase in enumerate(roadmap.phases):
            for sk in phase.skills:
                for prereq in sk.prerequisite_names:
                    prereq_idx = phase_order.get(prereq.lower())
                    if prereq_idx is not None and prereq_idx > p_idx:
                        ordering_violations += 1
        if ordering_violations > 0:
            dep_score = max(20.0, dep_score - (ordering_violations * 20.0))
            notes.append(f"{ordering_violations} prerequisite order violation(s) found across phases.")

        # 2. Goal alignment
        goal_score = 85.0
        if not roadmap.objective or len(roadmap.objective) < 10:
            goal_score -= 30.0
            notes.append("Roadmap objective is terse or missing.")
        if len(roadmap.phases) == 0:
            goal_score = 0.0

        # 3. Market alignment & Evidence strength
        all_skills = [sk for p in roadmap.phases for sk in p.skills]
        if evidence_summaries and all_skills:
            grounded_skills = [sk for sk in all_skills if sk.name in evidence_summaries and evidence_summaries[sk.name].evidence_count > 0]
            evidence_pct = len(grounded_skills) / len(all_skills)
            evidence_score = round(evidence_pct * 100.0, 1)

            # Average weighted score of grounded skills
            avg_w = sum(evidence_summaries[sk.name].weighted_score for sk in grounded_skills) / max(1, len(grounded_skills))
            market_score = round(avg_w * 100.0, 1)
        else:
            evidence_score = 50.0  # Default ungrounded baseline
            market_score = 60.0
            notes.append("Limited or no external market research evidence grounded.")

        # 4. Time feasibility
        # Check total estimated hours vs available study time
        total_hours = sum(sk.estimated_hours for sk in all_skills)
        weekly_hours = max(1.0, profile.study_hours_per_week)
        target_deadline_weeks = max(1.0, profile.deadline_months * 4.33)
        weeks_required = total_hours / weekly_hours

        if weeks_required <= target_deadline_weeks:
            time_score = 95.0
        elif weeks_required <= target_deadline_weeks * 1.25:
            time_score = 75.0
            notes.append(f"Estimated workload ({int(weeks_required)} wks) exceeds user deadline ({target_deadline_weeks} wks) by <25%.")
        elif weeks_required <= target_deadline_weeks * 1.5:
            time_score = 50.0
            notes.append(f"Estimated workload ({int(weeks_required)} wks) exceeds user deadline ({target_deadline_weeks} wks) by 25-50%.")
        else:
            time_score = 25.0
            notes.append(f"Workload highly infeasible: requires {int(weeks_required)} weeks vs deadline of {target_deadline_weeks} weeks.")

        # 5. Portfolio value
        total_projects = sum(len(p.projects) for p in roadmap.phases)
        if total_projects >= len(roadmap.phases):
            portfolio_score = 90.0
        elif total_projects > 0:
            portfolio_score = 70.0
        else:
            portfolio_score = 40.0
            notes.append("No portfolio projects included in roadmap.")

        # 6. Scope efficiency
        # Ratio of critical/high priority to overall skills
        high_pri = sum(1 for sk in all_skills if sk.priority.value in ("critical", "high"))
        efficiency = (high_pri / max(1, len(all_skills)))
        scope_score = round(max(50.0, min(100.0, efficiency * 100.0 + 20.0)), 1)

        # Composite overall score
        overall = (
            (goal_score * 0.20)
            + (market_score * 0.20)
            + (evidence_score * 0.15)
            + (dep_score * 0.15)
            + (time_score * 0.15)
            + (portfolio_score * 0.10)
            + (scope_score * 0.05)
        )

        return RoadmapQualityScore(
            overall_score=round(overall, 1),
            goal_alignment=round(goal_score, 1),
            market_alignment=round(market_score, 1),
            evidence_strength=round(evidence_score, 1),
            dependency_correctness=round(dep_score, 1),
            time_feasibility=round(time_score, 1),
            portfolio_value=round(portfolio_score, 1),
            scope_efficiency=round(scope_score, 1),
            scoring_notes=notes,
        )
