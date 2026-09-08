"""Tests: Feedback endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

_PROFILE_BODY = {
    "name": "Feedback User",
    "target_goal": "Learn data science from scratch",
    "current_level": "missing",
    "study_hours_per_day": 2.0,
    "deadline_months": 12,
}


def _create_profile(client: TestClient) -> str:
    resp = client.post("/api/v1/profiles", json=_PROFILE_BODY)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_record_feedback_no_roadmap(api_client: TestClient) -> None:
    """Feedback requires an existing roadmap."""
    pid = _create_profile(api_client)
    body = {
        "skill_name": "Python",
        "difficulty": 3,
        "confidence": 4,
        "satisfaction": 3,
    }
    resp = api_client.post(f"/api/v1/profiles/{pid}/feedback", json=body)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ROADMAP_NOT_FOUND"


def test_record_feedback_invalid_rating(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    body = {
        "skill_name": "Python",
        "difficulty": 10,  # invalid, max is 5
        "confidence": 3,
        "satisfaction": 3,
    }
    resp = api_client.post(f"/api/v1/profiles/{pid}/feedback", json=body)
    assert resp.status_code == 422


def test_record_feedback_no_profile(api_client: TestClient) -> None:
    body = {
        "skill_name": "Python",
        "difficulty": 3,
        "confidence": 3,
        "satisfaction": 3,
    }
    resp = api_client.post("/api/v1/profiles/nonexistent/feedback", json=body)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in ("RESOURCE_NOT_FOUND", "PROFILE_NOT_FOUND")


def test_record_feedback_missing_fields(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    # Missing skill_name
    body = {"difficulty": 3, "confidence": 3, "satisfaction": 3}
    resp = api_client.post(f"/api/v1/profiles/{pid}/feedback", json=body)
    assert resp.status_code == 422

