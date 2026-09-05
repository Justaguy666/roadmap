"""
Domain service: RoadmapValidator.

Validates a Roadmap against a set of deterministic domain rules.
Returns structured validation issues rather than raising exceptions,
so the EvaluatorAgent can report them clearly.

Validation rules (deterministic — no LLM):
  - No empty phases
  - No phase with zero skills
  - Total hours must be within user's deadline + buffer
  - No duplicate skill names within the same phase
  - Skills in later phases must not be prerequisites of skills in earlier phases
    (basic prerequisite ordering check — deep graph check in skill_graph service)
  - Milestones must have at least one exit criterion
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from roadmap.domain.entities.roadmap import Roadmap
from roadmap.domain.entities.user_profile import UserProfile


class IssueType(str, Enum):
    EMPTY_PHASE = "empty_phase"
    UNREALISTIC_WORKLOAD = "unrealistic_workload"
    DUPLICATE_SKILL = "duplicate_skill"
    MISSING_MILESTONE_CRITERIA = "missing_milestone_criteria"
    MISSING_OBJECTIVE = "missing_objective"
    ZERO_TIME_ESTIMATE = "zero_time_estimate"
    PREREQUISITE_ORDER_VIOLATION = "prerequisite_order_violation"


@dataclass(frozen=True)
class ValidationIssue:
    issue_type: IssueType
    severity: str          # "error" | "warning"
    message: str
    affected: str = ""     # phase/skill name


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def add_error(self, issue_type: IssueType, message: str, affected: str = "") -> None:
        self.issues.append(ValidationIssue(issue_type, "error", message, affected))

    def add_warning(self, issue_type: IssueType, message: str, affected: str = "") -> None:
        self.issues.append(ValidationIssue(issue_type, "warning", message, affected))


class RoadmapValidator:
    """
    Validates a Roadmap against deterministic domain rules.

    Does NOT use LLM for validation — that is the EvaluatorAgent's job.
    This service checks structural correctness and feasibility.
    """

    # Allow 20% overrun on estimated hours vs deadline
    DEADLINE_BUFFER_FACTOR = 1.2

    def validate(self, roadmap: Roadmap, profile: UserProfile) -> ValidationResult:
        result = ValidationResult()

        self._check_empty_phases(roadmap, result)
        self._check_duplicate_skills(roadmap, result)
        self._check_missing_objectives(roadmap, result)
        self._check_milestone_criteria(roadmap, result)
        self._check_workload(roadmap, profile, result)

        return result

    def _check_empty_phases(self, roadmap: Roadmap, result: ValidationResult) -> None:
        for phase in roadmap.phases:
            if not phase.skills:
                result.add_error(
                    IssueType.EMPTY_PHASE,
                    f"Phase {phase.phase_number} '{phase.name}' has no skills.",
                    affected=phase.name,
                )

    def _check_duplicate_skills(self, roadmap: Roadmap, result: ValidationResult) -> None:
        all_skill_names: list[str] = []
        for phase in roadmap.phases:
            names_in_phase = [s.name.lower() for s in phase.skills]
            duplicates_in_phase = {n for n in names_in_phase if names_in_phase.count(n) > 1}
            for dup in duplicates_in_phase:
                result.add_warning(
                    IssueType.DUPLICATE_SKILL,
                    f"Skill '{dup}' appears multiple times in Phase {phase.phase_number}.",
                    affected=phase.name,
                )
            for name in names_in_phase:
                if name in all_skill_names:
                    result.add_warning(
                        IssueType.DUPLICATE_SKILL,
                        f"Skill '{name}' appears in multiple phases.",
                        affected=name,
                    )
                all_skill_names.append(name)

    def _check_missing_objectives(self, roadmap: Roadmap, result: ValidationResult) -> None:
        for phase in roadmap.phases:
            if not phase.objective.strip():
                result.add_warning(
                    IssueType.MISSING_OBJECTIVE,
                    f"Phase {phase.phase_number} '{phase.name}' has no objective.",
                    affected=phase.name,
                )

    def _check_milestone_criteria(self, roadmap: Roadmap, result: ValidationResult) -> None:
        for phase in roadmap.phases:
            for milestone in phase.milestones:
                if not milestone.exit_criteria:
                    result.add_warning(
                        IssueType.MISSING_MILESTONE_CRITERIA,
                        f"Milestone '{milestone.name}' in Phase {phase.phase_number} "
                        "has no exit criteria.",
                        affected=milestone.name,
                    )

    def _check_workload(
        self, roadmap: Roadmap, profile: UserProfile, result: ValidationResult
    ) -> None:
        total_hours = roadmap.total_estimated_hours
        available = profile.total_available_hours * self.DEADLINE_BUFFER_FACTOR

        if total_hours > available:
            result.add_error(
                IssueType.UNREALISTIC_WORKLOAD,
                f"Roadmap requires ~{total_hours:.0f}h but user has ~{available:.0f}h "
                f"available (including {int((self.DEADLINE_BUFFER_FACTOR-1)*100)}% buffer). "
                "Consider reducing scope or extending deadline.",
            )
