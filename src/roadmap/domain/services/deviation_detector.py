"""Domain service: DeviationDetector.

Performs deterministic progress deviation analysis comparing planned vs. actual progress,
computing learning velocity, detecting blocked skills, and classifying schedule health.
"""

from __future__ import annotations

from roadmap.domain.entities.adaptation import DeviationReport, DeviationStatus
from roadmap.domain.entities.feedback import LearningFeedback
from roadmap.domain.entities.progress_record import ProgressRecord, ProgressStatus
from roadmap.domain.entities.roadmap import Roadmap


class DeviationDetector:
    """
    Deterministic deviation detection engine.
    Does not make LLM calls.
    """

    WARNING_DEVIATION_THRESHOLD = 0.20  # 20% behind schedule
    CRITICAL_DEVIATION_THRESHOLD = 0.40  # 40% behind schedule
    CRITICAL_VELOCITY_THRESHOLD = 0.50  # pace is less than 50% of expected

    def analyze_deviation(
        self,
        roadmap: Roadmap,
        progress_records: list[ProgressRecord],
        feedback_records: list[LearningFeedback] | None = None,
    ) -> DeviationReport:
        """
        Evaluate learning velocity, time spent, completion rates, and blockers.
        """
        record_map = {r.skill_id: r for r in progress_records}
        all_skills = roadmap.all_skills

        total_planned_hours = sum(s.estimated_hours for s in all_skills)
        total_actual_hours = sum(r.actual_hours for r in progress_records)

        # Calculate planned hours for completed/in-progress skills
        planned_hours_delivered = 0.0
        actual_hours_logged = 0.0
        blocked_skills: list[str] = []
        behind_skills: list[str] = []

        total_completion_pct_sum = 0.0
        for s in all_skills:
            rec = record_map.get(s.id)
            if rec:
                total_completion_pct_sum += rec.completion_percentage
                planned_hours_delivered += (rec.completion_percentage / 100.0) * s.estimated_hours
                actual_hours_logged += rec.actual_hours

                if rec.status == ProgressStatus.BLOCKED:
                    blocked_skills.append(s.name)
                elif rec.actual_hours > s.estimated_hours * 1.5 and rec.completion_percentage < 80.0:
                    behind_skills.append(s.name)
            else:
                pass

        actual_pct = (
            (total_completion_pct_sum / len(all_skills))
            if all_skills
            else 0.0
        )

        # Expected completion based on actual hours spent vs total planned hours
        if total_planned_hours > 0:
            expected_pct = min(100.0, (actual_hours_logged / total_planned_hours) * 100.0)
        else:
            expected_pct = actual_pct

        # Learning Velocity: planned hours completed / actual hours spent
        velocity_ratio = round(planned_hours_delivered / actual_hours_logged, 2) if actual_hours_logged > 0 else 1.0

        # Progress deviation: percentage points behind expected progress
        # Normalized as a fraction 0.0 - 1.0
        progress_deviation = round(max(0.0, (expected_pct - actual_pct) / 100.0), 3) if expected_pct > 0 else 0.0

        # Check feedback signals (e.g. blockers or repeated difficulty 5)
        high_difficulty_skills: list[str] = []
        if feedback_records:
            for fb in feedback_records:
                if fb.blocked_reason and fb.skill_name and fb.skill_name not in blocked_skills:
                    blocked_skills.append(fb.skill_name)
                if fb.difficulty >= 5 and fb.skill_name and fb.skill_name not in high_difficulty_skills:
                    high_difficulty_skills.append(fb.skill_name)

        # Classify status
        status = DeviationStatus.ON_TRACK
        issues: list[str] = []
        recommendations: list[str] = []

        if len(blocked_skills) > 1 or progress_deviation >= self.CRITICAL_DEVIATION_THRESHOLD or (actual_hours_logged >= 10.0 and velocity_ratio <= self.CRITICAL_VELOCITY_THRESHOLD):
            status = DeviationStatus.CRITICAL
        elif len(blocked_skills) == 1 or progress_deviation >= self.WARNING_DEVIATION_THRESHOLD or (actual_hours_logged >= 10.0 and velocity_ratio < 0.75) or high_difficulty_skills:
            status = DeviationStatus.WARNING

        if blocked_skills:
            issues.append(f"Blocked skills detected: {', '.join(blocked_skills)}")
            recommendations.append("Consider breaking down blocked skills or providing prerequisite tutorials.")

        if progress_deviation >= self.WARNING_DEVIATION_THRESHOLD:
            issues.append(f"Learning pace is {int(progress_deviation * 100)}% behind planned timeline.")
            recommendations.append("Adjust weekly study hour expectations or extend phase timelines.")

        if velocity_ratio < 0.75 and actual_hours_logged >= 10.0:
            issues.append(f"Velocity ratio is low ({velocity_ratio}x): tasks take longer than estimated.")
            recommendations.append("Increase estimated hours per skill to match real-world acquisition speed.")

        if not issues:
            recommendations.append("Keep up the steady pace! Progress matches planned trajectory.")

        return DeviationReport(
            roadmap_id=roadmap.id,
            profile_id=roadmap.profile_id,
            status=status,
            total_planned_hours=round(total_planned_hours, 1),
            total_actual_hours=round(total_actual_hours, 1),
            expected_completion_percentage=round(expected_pct, 1),
            actual_completion_percentage=round(actual_pct, 1),
            velocity_ratio=velocity_ratio,
            progress_deviation=progress_deviation,
            blocked_skills=blocked_skills,
            behind_skills=behind_skills,
            issues=issues,
            recommendations=recommendations,
        )
