"""Use cases for querying roadmaps."""

from __future__ import annotations

from roadmap.application.ports.repositories import RoadmapRepository
from roadmap.domain.entities.roadmap import Roadmap
from roadmap.domain.exceptions import RoadmapNotFoundError


class ListRoadmapsUseCase:
    """List all roadmap versions for a profile."""

    def __init__(self, roadmap_repo: RoadmapRepository) -> None:
        self._roadmap_repo = roadmap_repo

    def execute(self, profile_id: str) -> list[Roadmap]:
        return self._roadmap_repo.load_all(profile_id)


class GetLatestRoadmapUseCase:
    """Load the latest roadmap version for a profile."""

    def __init__(self, roadmap_repo: RoadmapRepository) -> None:
        self._roadmap_repo = roadmap_repo

    def execute(self, profile_id: str) -> Roadmap:
        roadmap = self._roadmap_repo.load_latest(profile_id)
        if roadmap is None:
            raise RoadmapNotFoundError("No roadmap found for this profile.")
        return roadmap


class GetRoadmapByVersionUseCase:
    """Load a specific roadmap version for a profile."""

    def __init__(self, roadmap_repo: RoadmapRepository) -> None:
        self._roadmap_repo = roadmap_repo

    def execute(self, profile_id: str, version: int) -> Roadmap:
        roadmap = self._roadmap_repo.load_by_version(profile_id, version)
        if roadmap is None:
            raise RoadmapNotFoundError(f"Roadmap version {version} not found.")
        return roadmap
