"""Feedback endpoint: POST /api/v1/profiles/{profile_id}/feedback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from roadmap.api.dependencies import get_get_profile_use_case, get_record_feedback_use_case
from roadmap.api.schemas.feedback import FeedbackCreateRequest, FeedbackResponse
from roadmap.application.use_cases.profile_use_cases import GetProfileUseCase
from roadmap.application.use_cases.record_feedback import RecordFeedbackUseCase
from roadmap.domain.entities.feedback import LearningFeedback
from roadmap.domain.exceptions import ProfileNotFoundError, RoadmapNotFoundError

router = APIRouter(tags=["Feedback"])


def _feedback_to_response(f: LearningFeedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=f.id,
        profile_id=f.profile_id,
        roadmap_id=f.roadmap_id,
        skill_name=f.skill_name,
        difficulty=f.difficulty,
        confidence=f.confidence,
        satisfaction=f.satisfaction,
        blocked_reason=f.blocked_reason,
        free_text=f.free_text,
        created_at=f.created_at,
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


@router.post(
    "/profiles/{profile_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit qualitative learning feedback",
    description=(
        "Records qualitative feedback for a skill. "
        "Ratings (difficulty, confidence, satisfaction) must be 1-5. "
        "Requires an existing roadmap."
    ),
    responses={
        400: {"description": "Validation error"},
        404: {"description": "Profile or roadmap not found"},
    },
)
def record_feedback(
    profile_id: str,
    body: FeedbackCreateRequest,
    profile_uc: GetProfileUseCase = Depends(get_get_profile_use_case),
    use_case: RecordFeedbackUseCase = Depends(get_record_feedback_use_case),
) -> FeedbackResponse:
    _resolve_profile(profile_id, profile_uc)
    try:
        feedback = use_case.execute(
            profile_id=profile_id,
            skill_identifier=body.skill_name,
            difficulty=body.difficulty,
            confidence=body.confidence,
            satisfaction=body.satisfaction,
            blocked_reason=body.blocked_reason,
            free_text=body.free_text,
        )
        return _feedback_to_response(feedback)
    except (ValueError, RoadmapNotFoundError) as exc:
        msg = str(exc)
        if "no active roadmap" in msg.lower() or "roadmap" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ROADMAP_NOT_FOUND", "message": "No roadmap found for this profile"}},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": msg}},
        ) from exc
