"""Adaptation endpoint: POST /api/v1/profiles/{profile_id}/adaptations/prepare."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from roadmap.api.dependencies import get_adapt_roadmap_use_case, get_authorized_profile
from roadmap.api.schemas.adaptations import AdaptationProposalResponse, DeviationReportResponse
from roadmap.api.schemas.common import ErrorCode
from roadmap.application.use_cases.adapt_roadmap import AdaptRoadmapUseCase
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import RoadmapNotFoundError

router = APIRouter(tags=["Adaptations"])


@router.post(
    "/profiles/{profile_id}/adaptations/prepare",
    response_model=AdaptationProposalResponse,
    summary="Prepare a roadmap adaptation proposal",
    description=(
        "Analyses current progress and feedback to detect deviations, "
        "then generates a minimal adaptation proposal. "
        "\n\n"
        "**IMPORTANT INVARIANTS:**\n"
        "- This endpoint does NOT automatically persist a new roadmap version.\n"
        "- It does NOT mutate the current roadmap.\n"
        "- It respects anti-oscillation guards.\n"
        "- It respects evidence validation and graph validation.\n"
        "- Approval and persistence is a separate operation (MVP-7.3+).\n"
    ),
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Profile or roadmap not found"},
        409: {"description": "Anti-oscillation guard blocked the proposal"},
    },
)
def prepare_adaptation(
    force: bool = False,
    profile: UserProfile = Depends(get_authorized_profile),
    use_case: AdaptRoadmapUseCase = Depends(get_adapt_roadmap_use_case),
) -> AdaptationProposalResponse:
    """
    Prepare a roadmap adaptation proposal without persisting it.

    The proposal is returned to the caller for review.
    Approval/persistence must be performed as a separate explicit step.
    """
    try:
        result = use_case.prepare_adaptation(profile_id=profile.id, force=force)
    except RoadmapNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": ErrorCode.ROADMAP_NOT_FOUND, "message": "No roadmap found for this profile"}},
        ) from exc
    except ValueError as exc:
        msg = str(exc)
        if "roadmap" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": ErrorCode.ROADMAP_NOT_FOUND, "message": "No roadmap found for this profile"}},
            ) from exc
        # Anti-oscillation guard raises ValueError with a descriptive message
        if "oscillation" in msg.lower() or "too soon" in msg.lower() or "recently" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "ANTI_OSCILLATION_BLOCKED", "message": msg}},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": ErrorCode.BAD_REQUEST, "message": msg}},
        ) from exc


    dev = result.deviation_report
    proposal = result.proposal

    deviation_response = DeviationReportResponse(
        roadmap_id=dev.roadmap_id,
        profile_id=dev.profile_id,
        status=dev.status.value if hasattr(dev.status, "value") else str(dev.status),
        total_planned_hours=dev.total_planned_hours,
        total_actual_hours=dev.total_actual_hours,
        expected_completion_percentage=dev.expected_completion_percentage,
        actual_completion_percentage=dev.actual_completion_percentage,
        velocity_ratio=dev.velocity_ratio,
        progress_deviation=dev.progress_deviation,
        blocked_skills=dev.blocked_skills,
        behind_skills=dev.behind_skills,
        issues=dev.issues,
        recommendations=dev.recommendations,
        analyzed_at=dev.analyzed_at,
        requires_adaptation=dev.requires_adaptation,
    )

    # Extract proposal summary and proposed changes
    adaptation_needed = dev.requires_adaptation
    anti_oscillation_blocked = False
    proposal_summary = ""
    proposed_changes: list[str] = []
    message = ""

    if proposal is None:
        anti_oscillation_blocked = True
        message = "Anti-oscillation guard prevented proposal generation. No recent significant deviation detected."
    else:
        # proposal is an AdaptationProposal dataclass
        proposal_summary = getattr(proposal, "rationale", "") or getattr(proposal, "summary", "")
        raw_changes = getattr(proposal, "proposed_changes", None) or getattr(proposal, "changes", [])
        if isinstance(raw_changes, list):
            proposed_changes = [str(c) for c in raw_changes]
        elif isinstance(raw_changes, dict):
            proposed_changes = [f"{k}: {v}" for k, v in raw_changes.items()]

    return AdaptationProposalResponse(
        profile_id=profile.id,
        deviation_report=deviation_response,
        adaptation_needed=adaptation_needed,
        proposal_summary=proposal_summary,
        proposed_changes=proposed_changes,
        anti_oscillation_blocked=anti_oscillation_blocked,
        message=message,
    )
