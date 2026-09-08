"""Profile endpoints: POST /api/v1/profiles, GET /api/v1/profiles/{profile_id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from roadmap.api.dependencies import (
    get_authorized_profile,
    get_create_profile_use_case,
    get_current_user,
)
from roadmap.api.schemas.common import ErrorCode
from roadmap.api.schemas.profiles import ProfileCreateRequest, ProfileResponse
from roadmap.application.use_cases.profile_use_cases import (
    CreateProfileRequest,
    CreateProfileUseCase,
)
from roadmap.domain.entities.user import User
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import ProfileAlreadyExistsError

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
        "Creates a new user profile bound to the authenticated user. "
        "Returns 409 if a profile already exists for this user."
    ),
    responses={
        401: {"description": "Authentication required"},
        409: {"description": "Profile already exists"},
        422: {"description": "Validation error"},
    },
)
def create_profile(
    body: ProfileCreateRequest,
    current_user: User = Depends(get_current_user),
    use_case: CreateProfileUseCase = Depends(get_create_profile_use_case),
) -> ProfileResponse:
    """Create a new user profile for the authenticated user."""
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
        profile = use_case.execute(request, user_id=current_user.id)
        return _profile_to_response(profile)
    except ProfileAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": ErrorCode.PROFILE_ALREADY_EXISTS, "message": str(exc)}},
        ) from exc


@router.get(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="Retrieve a user profile by ID",
    description=(
        "Returns the user profile for the given profile_id if owned by caller. "
        "Returns 404 if no profile exists or the profile belongs to another user."
    ),
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Resource not found"},
    },
)
def get_profile(
    profile: UserProfile = Depends(get_authorized_profile),
) -> ProfileResponse:
    """Retrieve profile by ID (authorized for caller)."""
    return _profile_to_response(profile)

