"""Profile endpoints: POST /api/v1/profiles, GET /api/v1/profiles/{profile_id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from roadmap.api.dependencies import get_create_profile_use_case, get_get_profile_use_case
from roadmap.api.schemas.profiles import ProfileCreateRequest, ProfileResponse
from roadmap.application.use_cases.profile_use_cases import (
    CreateProfileRequest,
    CreateProfileUseCase,
    GetProfileUseCase,
)
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import ProfileAlreadyExistsError, ProfileNotFoundError

router = APIRouter(prefix="/profiles", tags=["Profiles"])


def _profile_to_response(p: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        id=p.id,
        name=p.name,
        target_goal=p.target_goal,
        target_role=p.target_role,
        current_level=p.current_level.value if hasattr(p.current_level, "value") else str(p.current_level),
        current_skills=p.current_skills,
        programming_languages=p.programming_languages,
        previous_experience=p.previous_experience,
        completed_projects=p.completed_projects,
        preferred_technologies=p.preferred_technologies,
        preferred_industry=p.preferred_industry,
        target_markets=p.target_markets,
        learning_preferences=p.learning_preferences,
        budget=p.budget.value if hasattr(p.budget, "value") else str(p.budget),
        constraints=p.constraints,
        study_hours_per_day=p.study_hours_per_day,
        deadline_months=p.deadline_months,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user profile",
    description=(
        "Creates a new user profile. "
        "Returns 409 if a profile already exists (single-user system). "
        "Authentication: NOT YET IMPLEMENTED (MVP-7.3)."
    ),
    responses={
        409: {"description": "Profile already exists"},
        422: {"description": "Validation error"},
    },
)
def create_profile(
    body: ProfileCreateRequest,
    use_case: CreateProfileUseCase = Depends(get_create_profile_use_case),
) -> ProfileResponse:
    """Create a new user profile."""
    try:
        request = CreateProfileRequest(
            name=body.name,
            target_goal=body.target_goal,
            target_role=body.target_role,
            current_level=body.current_level,
            current_skills=body.current_skills,
            programming_languages=body.programming_languages,
            previous_experience=body.previous_experience,
            completed_projects=body.completed_projects,
            preferred_technologies=body.preferred_technologies,
            preferred_industry=body.preferred_industry,
            target_markets=body.target_markets,
            learning_preferences=body.learning_preferences,
            budget=body.budget,
            constraints=body.constraints,
            study_hours_per_day=body.study_hours_per_day,
            deadline_months=body.deadline_months,
        )
        profile = use_case.execute(request)
        return _profile_to_response(profile)
    except ProfileAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "PROFILE_ALREADY_EXISTS", "message": str(exc)}},
        ) from exc


@router.get(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="Retrieve a user profile by ID",
    description=(
        "Returns the user profile for the given profile_id. "
        "Returns 404 if no profile exists or the ID does not match. "
        "Authentication: NOT YET IMPLEMENTED (MVP-7.3)."
    ),
    responses={
        404: {"description": "Profile not found"},
    },
)
def get_profile(
    profile_id: str,
    use_case: GetProfileUseCase = Depends(get_get_profile_use_case),
) -> ProfileResponse:
    """Retrieve profile by ID."""
    try:
        profile = use_case.execute()
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found"}},
        ) from exc

    # Single-user system: verify the path ID matches the stored profile
    if profile.id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found"}},
        )

    return _profile_to_response(profile)
