"""Tests: Roadmap endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

_PROFILE_BODY = {
    "name": "Dev User",
    "target_goal": "Become a Python developer",
    "current_level": "missing",
    "study_hours_per_day": 3.0,
    "deadline_months": 6,
}


def _create_profile(client: TestClient) -> str:
    resp = client.post("/api/v1/profiles", json=_PROFILE_BODY)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_list_roadmaps_empty(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    resp = api_client.get(f"/api/v1/profiles/{pid}/roadmaps")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_roadmaps_no_profile(api_client: TestClient) -> None:
    resp = api_client.get("/api/v1/profiles/nonexistent/roadmaps")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROFILE_NOT_FOUND"


def test_get_latest_roadmap_not_found(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    resp = api_client.get(f"/api/v1/profiles/{pid}/roadmaps/latest")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ROADMAP_NOT_FOUND"


def test_get_roadmap_by_version_not_found(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    resp = api_client.get(f"/api/v1/profiles/{pid}/roadmaps/99")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ROADMAP_NOT_FOUND"


def test_list_roadmaps_nonexistent_profile(api_client: TestClient) -> None:
    resp = api_client.get("/api/v1/profiles/bad-id/roadmaps")
    assert resp.status_code == 404

