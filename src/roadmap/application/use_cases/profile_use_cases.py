"""
Application use case: CreateProfile / GetProfile / UpdateProfile.

These are the only entry points for profile management.
The CLI calls these use cases — never the repository directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from roadmap.application.ports.repositories import ProfileRepository
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import ProfileAlreadyExistsError, ProfileNotFoundError
from roadmap.domain.value_objects import BudgetPreference, SkillLevel
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CreateProfileRequest:
    name: str
    target_goal: str
    target_role: str = ""
    current_level: SkillLevel = SkillLevel.MISSING
    current_skills: list[str] | None = None
    programming_languages: list[str] | None = None
    previous_experience: str = ""
    completed_projects: list[str] | None = None
    preferred_technologies: list[str] | None = None
    preferred_industry: str = ""
    target_markets: list[str] | None = None
    learning_preferences: list[str] | None = None
    budget: BudgetPreference = BudgetPreference.ANY
    constraints: list[str] | None = None
    study_hours_per_day: float = 2.0
    deadline_months: int = 12


class CreateProfileUseCase:
    """Creates a new user profile. Raises if one already exists."""

    def __init__(self, profile_repo: ProfileRepository) -> None:
        self._repo = profile_repo

    def execute(self, request: CreateProfileRequest, overwrite: bool = False) -> UserProfile:
        if self._repo.exists() and not overwrite:
            raise ProfileAlreadyExistsError(
                "A profile already exists. Use `roadmap profile --reset` to start over, "
                "or `roadmap profile edit` to update it."
            )

        profile = UserProfile(
            id=new_id(),
            name=request.name,
            target_goal=request.target_goal,
            target_role=request.target_role,
            current_level=request.current_level,
            current_skills=request.current_skills or [],
            programming_languages=request.programming_languages or [],
            previous_experience=request.previous_experience,
            completed_projects=request.completed_projects or [],
            preferred_technologies=request.preferred_technologies or [],
            preferred_industry=request.preferred_industry,
            target_markets=request.target_markets or [],
            learning_preferences=request.learning_preferences or [],
            budget=request.budget,
            constraints=request.constraints or [],
            study_hours_per_day=request.study_hours_per_day,
            deadline_months=request.deadline_months,
        )

        self._repo.save(profile)
        logger.info("Profile created", profile_id=profile.id, name=profile.name)
        return profile


class GetProfileUseCase:
    """Load the current profile. Raises if none exists."""

    def __init__(self, profile_repo: ProfileRepository) -> None:
        self._repo = profile_repo

    def execute(self) -> UserProfile:
        profile = self._repo.load()
        if profile is None:
            raise ProfileNotFoundError(
                "No profile found. Run `roadmap init` to create one."
            )
        return profile


@dataclass
class UpdateProfileRequest:
    """Fields to update — None means keep existing value."""

    name: str | None = None
    target_goal: str | None = None
    target_role: str | None = None
    current_level: SkillLevel | None = None
    current_skills: list[str] | None = None
    programming_languages: list[str] | None = None
    previous_experience: str | None = None
    completed_projects: list[str] | None = None
    preferred_technologies: list[str] | None = None
    preferred_industry: str | None = None
    target_markets: list[str] | None = None
    learning_preferences: list[str] | None = None
    budget: BudgetPreference | None = None
    constraints: list[str] | None = None
    study_hours_per_day: float | None = None
    deadline_months: int | None = None


class UpdateProfileUseCase:
    """Update specific fields of an existing profile."""

    def __init__(self, profile_repo: ProfileRepository) -> None:
        self._repo = profile_repo

    def execute(self, request: UpdateProfileRequest) -> UserProfile:
        profile = self._repo.load()
        if profile is None:
            raise ProfileNotFoundError("No profile found. Run `roadmap init` first.")

        # Apply only non-None fields
        if request.name is not None:
            profile.name = request.name
        if request.target_goal is not None:
            profile.target_goal = request.target_goal
        if request.target_role is not None:
            profile.target_role = request.target_role
        if request.current_level is not None:
            profile.current_level = request.current_level
        if request.current_skills is not None:
            profile.current_skills = request.current_skills
        if request.programming_languages is not None:
            profile.programming_languages = request.programming_languages
        if request.previous_experience is not None:
            profile.previous_experience = request.previous_experience
        if request.completed_projects is not None:
            profile.completed_projects = request.completed_projects
        if request.preferred_technologies is not None:
            profile.preferred_technologies = request.preferred_technologies
        if request.preferred_industry is not None:
            profile.preferred_industry = request.preferred_industry
        if request.target_markets is not None:
            profile.target_markets = request.target_markets
        if request.learning_preferences is not None:
            profile.learning_preferences = request.learning_preferences
        if request.budget is not None:
            profile.budget = request.budget
        if request.constraints is not None:
            profile.constraints = request.constraints
        if request.study_hours_per_day is not None:
            profile.study_hours_per_day = request.study_hours_per_day
        if request.deadline_months is not None:
            profile.deadline_months = request.deadline_months

        profile.touch()
        self._repo.save(profile)
        logger.info("Profile updated", profile_id=profile.id)
        return profile


class DeleteProfileUseCase:
    """Delete the active user profile."""

    def __init__(self, profile_repo: ProfileRepository) -> None:
        self._repo = profile_repo

    def execute(self) -> None:
        self._repo.delete()
        logger.info("Profile deleted")
