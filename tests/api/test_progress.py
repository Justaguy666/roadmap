"""Tests: Progress endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

_PROFILE_BODY = {
    "name": "Progress User",
    "target_goal": "Learn machine learning",
    "current_level": "missing",
    "study_hours_per_day": 2.0,
    "deadline_months": 12,
}


def _create_profile(client: TestClient) -> str:
    resp = client.post("/api/v1/profiles", json=_PROFILE_BODY)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_list_progress_empty(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    resp = api_client.get(f"/api/v1/profiles/{pid}/progress")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_progress_no_profile(api_client: TestClient) -> None:
    resp = api_client.get("/api/v1/profiles/nonexistent/progress")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in ("RESOURCE_NOT_FOUND", "PROFILE_NOT_FOUND")


def test_record_progress_no_roadmap(api_client: TestClient) -> None:
    """Progress recording requires an existing roadmap."""
    pid = _create_profile(api_client)
    body = {
        "skill_name": "Python",
        "completion_percentage": 50.0,
    }
    resp = api_client.post(f"/api/v1/profiles/{pid}/progress", json=body)
    # No roadmap -> 404 ROADMAP_NOT_FOUND or 400 SKILL_NOT_FOUND depending on implementation
    assert resp.status_code in (400, 404)


def test_record_progress_invalid_percentage(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    body = {
        "skill_name": "Python",
        "completion_percentage": 150.0,  # invalid
    }
    resp = api_client.post(f"/api/v1/profiles/{pid}/progress", json=body)
    assert resp.status_code == 422


def test_record_progress_missing_skill_name(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    body = {"completion_percentage": 50.0}
    resp = api_client.post(f"/api/v1/profiles/{pid}/progress", json=body)
    assert resp.status_code == 422


def test_record_progress_no_profile(api_client: TestClient) -> None:
    body = {
        "skill_name": "Python",
        "completion_percentage": 50.0,
    }
    resp = api_client.post("/api/v1/profiles/nonexistent/progress", json=body)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in ("RESOURCE_NOT_FOUND", "PROFILE_NOT_FOUND")

