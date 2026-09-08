"""Feedback endpoint: POST /api/v1/profiles/{profile_id}/feedback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from roadmap.api.dependencies import get_authorized_profile, get_record_feedback_use_case
from roadmap.api.schemas.common import ErrorCode
from roadmap.api.schemas.feedback import FeedbackCreateRequest, FeedbackResponse
from roadmap.application.use_cases.record_feedback import RecordFeedbackUseCase
from roadmap.domain.entities.feedback import LearningFeedback
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import RoadmapNotFoundError

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
        401: {"description": "Authentication required"},
        404: {"description": "Profile or roadmap not found"},
    },
)
def record_feedback(
    body: FeedbackCreateRequest,
    profile: UserProfile = Depends(get_authorized_profile),
    use_case: RecordFeedbackUseCase = Depends(get_record_feedback_use_case),
) -> FeedbackResponse:
    try:
        feedback = use_case.execute(
            profile_id=profile.id,
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
                detail={"error": {"code": ErrorCode.ROADMAP_NOT_FOUND, "message": "No roadmap found for this profile"}},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": ErrorCode.VALIDATION_ERROR, "message": msg}},
        ) from exc

