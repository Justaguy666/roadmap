"""Roadmap endpoints: list, latest, by version."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from roadmap.api.dependencies import (
    get_authorized_profile,
    get_get_latest_roadmap_use_case,
    get_get_roadmap_by_version_use_case,
    get_list_roadmaps_use_case,
)
from roadmap.api.schemas.common import ErrorCode
from roadmap.api.schemas.roadmaps import (
    MilestoneResponse,
    PhaseResponse,
    RoadmapResponse,
    RoadmapSummaryResponse,
)
from roadmap.application.use_cases.roadmap_use_cases import (
    GetLatestRoadmapUseCase,
    GetRoadmapByVersionUseCase,
    ListRoadmapsUseCase,
)
from roadmap.domain.entities.roadmap import Roadmap
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.exceptions import RoadmapNotFoundError

router = APIRouter(tags=["Roadmaps"])


def _roadmap_to_response(r: Roadmap) -> RoadmapResponse:
    phases = []
    for phase in r.phases:
        milestones = [
            MilestoneResponse(
                id=m.id,
                name=m.name,
                description=m.description,
                exit_criteria=m.exit_criteria,
                estimated_weeks=m.estimated_weeks,
                is_achieved=m.is_achieved,
            )
            for m in phase.milestones
        ]
        skill_names = [s.name for s in phase.skills]
        phases.append(
            PhaseResponse(
                id=phase.id,
                phase_number=phase.phase_number,
                name=phase.name,
                objective=phase.objective,
                estimated_weeks=phase.estimated_weeks,
                skill_names=skill_names,
                milestones=milestones,
            )
        )
    return RoadmapResponse(
        id=r.id,
        profile_id=r.profile_id,
        title=r.title,
        version=r.version,
        objective=r.objective,
        quality_score=r.quality_score,
        validation_status=r.validation_status.value if hasattr(r.validation_status, "value") else str(r.validation_status),
        generated_at=r.generated_at,
        last_updated_at=r.last_updated_at,
        phases=phases,
    )


def _roadmap_to_summary(r: Roadmap) -> RoadmapSummaryResponse:
    return RoadmapSummaryResponse(
        id=r.id,
        profile_id=r.profile_id,
        title=r.title,
        version=r.version,
        objective=r.objective,
        quality_score=r.quality_score,
        validation_status=r.validation_status.value if hasattr(r.validation_status, "value") else str(r.validation_status),
        generated_at=r.generated_at,
        last_updated_at=r.last_updated_at,
    )


@router.get(
    "/profiles/{profile_id}/roadmaps",
    response_model=list[RoadmapSummaryResponse],
    summary="List all roadmap versions for a profile",
    description="Returns summaries of all roadmap versions. Versions are immutable once created.",
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Resource not found"},
    },
)
def list_roadmaps(
    profile: UserProfile = Depends(get_authorized_profile),
    use_case: ListRoadmapsUseCase = Depends(get_list_roadmaps_use_case),
) -> list[RoadmapSummaryResponse]:
    roadmaps = use_case.execute(profile.id)
    return [_roadmap_to_summary(r) for r in roadmaps]


@router.get(
    "/profiles/{profile_id}/roadmaps/latest",
    response_model=RoadmapResponse,
    summary="Retrieve the latest roadmap version",
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "No roadmap or profile found"},
    },
)
def get_latest_roadmap(
    profile: UserProfile = Depends(get_authorized_profile),
    use_case: GetLatestRoadmapUseCase = Depends(get_get_latest_roadmap_use_case),
) -> RoadmapResponse:
    try:
        roadmap = use_case.execute(profile.id)
    except RoadmapNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": ErrorCode.ROADMAP_NOT_FOUND, "message": "No roadmap found for this profile"}},
        ) from exc
    return _roadmap_to_response(roadmap)


@router.get(
    "/profiles/{profile_id}/roadmaps/{version}",
    response_model=RoadmapResponse,
    summary="Retrieve a specific roadmap version",
    description="Roadmap versions are immutable. Version numbers start at 1.",
    responses={
        401: {"description": "Authentication required"},
        404: {"description": "Roadmap version or profile not found"},
    },
)
def get_roadmap_by_version(
    version: int,
    profile: UserProfile = Depends(get_authorized_profile),
    use_case: GetRoadmapByVersionUseCase = Depends(get_get_roadmap_by_version_use_case),
) -> RoadmapResponse:
    try:
        roadmap = use_case.execute(profile.id, version)
    except RoadmapNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": ErrorCode.ROADMAP_NOT_FOUND, "message": f"Roadmap version {version} not found"}},
        ) from exc
    return _roadmap_to_response(roadmap)


