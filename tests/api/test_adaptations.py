"""Tests: Adaptation endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

_PROFILE_BODY = {
    "name": "Adapt User",
    "target_goal": "Transition to DevOps engineer",
    "current_level": "missing",
    "study_hours_per_day": 2.0,
    "deadline_months": 12,
}


def _create_profile(client: TestClient) -> str:
    resp = client.post("/api/v1/profiles", json=_PROFILE_BODY)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_prepare_adaptation_no_roadmap(api_client: TestClient) -> None:
    """Adaptation requires a roadmap — returns 404 without one."""
    pid = _create_profile(api_client)
    resp = api_client.post(f"/api/v1/profiles/{pid}/adaptations/prepare")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ROADMAP_NOT_FOUND"


def test_prepare_adaptation_no_profile(api_client: TestClient) -> None:
    resp = api_client.post("/api/v1/profiles/nonexistent/adaptations/prepare")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROFILE_NOT_FOUND"

