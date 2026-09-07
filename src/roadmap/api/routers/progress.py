"""Progress endpoints: GET/POST /api/v1/profiles/{profile_id}/progress."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from roadmap.api.dependencies import (
    get_get_profile_use_case,
    get_list_progress_use_case,
    get_record_progress_use_case,
)
from roadmap.api.schemas.progress import ProgressCreateRequest, ProgressResponse
from roadmap.application.use_cases.profile_use_cases import GetProfileUseCase
from roadmap.application.use_cases.record_progress import (
    ListProgressUseCase,
    UpdateProgressUseCase,
)
from roadmap.domain.entities.progress_record import ProgressRecord
from roadmap.domain.exceptions import (
    InvalidProgressError,
    ProfileNotFoundError,
    RoadmapNotFoundError,
    SkillNotFoundError,
)

router = APIRouter(tags=["Progress"])


def _progress_to_response(p: ProgressRecord) -> ProgressResponse:
    return ProgressResponse(
        id=p.id,
        profile_id=p.profile_id,
        skill_id=p.skill_id,
        skill_name=p.skill_name,
        phase_id=p.phase_id,
        status=p.status.value if hasattr(p.status, "value") else str(p.status),
        completion_percentage=p.completion_percentage,
        planned_hours=p.planned_hours,
        actual_hours=p.actual_hours,
        started_at=p.started_at,
        completed_at=p.completed_at,
        notes=p.notes,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _resolve_profile(profile_id: str, profile_uc: GetProfileUseCase) -> None:
    try:
        profile = profile_uc.execute()
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found"}},
        ) from exc
    if profile.id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROFILE_NOT_FOUND", "message": "Profile not found"}},
        )


@router.get(
    "/profiles/{profile_id}/progress",
    response_model=list[ProgressResponse],
    summary="List all progress records for a profile",
    description="Returns all progress records for the profile.",
)
def list_progress(
    profile_id: str,
    profile_uc: GetProfileUseCase = Depends(get_get_profile_use_case),
    use_case: ListProgressUseCase = Depends(get_list_progress_use_case),
) -> list[ProgressResponse]:
    _resolve_profile(profile_id, profile_uc)
    records = use_case.execute(profile_id)
    return [_progress_to_response(r) for r in records]


@router.post(
    "/profiles/{profile_id}/progress",
    response_model=ProgressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a skill progress update",
    description=(
        "Records a progress update for a skill. "
        "The skill must exist in the latest roadmap. "
        "completion_percentage must be 0-100."
    ),
    responses={
        400: {"description": "Invalid progress or skill not found"},
        404: {"description": "Profile or roadmap not found"},
    },
)
def record_progress(
    profile_id: str,
    body: ProgressCreateRequest,
    profile_uc: GetProfileUseCase = Depends(get_get_profile_use_case),
    use_case: UpdateProgressUseCase = Depends(get_record_progress_use_case),
) -> ProgressResponse:
    _resolve_profile(profile_id, profile_uc)
    try:
        result = use_case.execute(
            profile_id=profile_id,
            skill_identifier=body.skill_name,
            percentage=body.completion_percentage,
            actual_hours=body.actual_hours,
            status=body.status,
            notes=body.notes,
        )
        return _progress_to_response(result.record)
    except (RoadmapNotFoundError, ValueError) as exc:
        msg = str(exc)
        if "roadmap" in msg.lower() or isinstance(exc, RoadmapNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ROADMAP_NOT_FOUND", "message": "No roadmap found for this profile"}},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "BAD_REQUEST", "message": msg}},
        ) from exc
    except SkillNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "SKILL_NOT_FOUND", "message": str(exc)}},
        ) from exc
    except InvalidProgressError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_PROGRESS", "message": str(exc)}},
        ) from exc
