"""Domain exception hierarchy.

All domain errors derive from RoadmapDomainError.
They carry no external library dependencies.
"""

from __future__ import annotations


class RoadmapDomainError(Exception):
    """Base class for all domain errors."""


class ProfileNotFoundError(RoadmapDomainError):
    """Raised when a user profile cannot be found."""


class ProfileAlreadyExistsError(RoadmapDomainError):
    """Raised when trying to create a profile that already exists."""


class RoadmapNotFoundError(RoadmapDomainError):
    """Raised when no roadmap exists for the current profile."""


class SkillNotFoundError(RoadmapDomainError):
    """Raised when a referenced skill does not exist."""

    def __init__(self, skill_name: str) -> None:
        self.skill_name = skill_name
        super().__init__(f"Skill not found: {skill_name!r}")


class SkillGraphCycleError(RoadmapDomainError):
    """Raised when the skill dependency graph contains a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(
            f"Skill dependency cycle detected: {' → '.join(cycle)}"
        )


class InvalidProgressError(RoadmapDomainError):
    """Raised when a progress update is invalid."""


class GoalNotAnalyzedError(RoadmapDomainError):
    """Raised when goal analysis is required but hasn't been performed yet."""


class ResearchRequiredError(RoadmapDomainError):
    """Raised when an operation requires research that hasn't been run yet."""


class ValidationError(RoadmapDomainError):
    """Raised when domain validation fails."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"Validation error on '{field}': {message}")


class RoadmapValidationError(RoadmapDomainError):
    """Raised when a generated roadmap fails deterministic domain validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        formatted = "; ".join(errors)
        super().__init__(f"Roadmap failed validation: {formatted}")
