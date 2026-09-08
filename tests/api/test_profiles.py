"""Tests: Profile endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

_VALID_BODY = {
    "name": "Test User",
    "target_goal": "Become a software engineer",
    "current_level": "missing",
    "study_hours_per_day": 2.0,
    "deadline_months": 12,
}


def test_create_profile_success(api_client: TestClient) -> None:
    resp = api_client.post("/api/v1/profiles", json=_VALID_BODY)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test User"
    assert data["target_goal"] == "Become a software engineer"
    assert "id" in data
    assert "created_at" in data


def test_create_profile_conflict(api_client: TestClient) -> None:
    """Creating a second profile returns 409."""
    api_client.post("/api/v1/profiles", json=_VALID_BODY)
    resp = api_client.post("/api/v1/profiles", json=_VALID_BODY)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROFILE_ALREADY_EXISTS"


def test_create_profile_missing_name(api_client: TestClient) -> None:
    body = {**_VALID_BODY}
    body.pop("name")
    resp = api_client.post("/api/v1/profiles", json=body)
    assert resp.status_code == 422


def test_create_profile_short_goal(api_client: TestClient) -> None:
    body = {**_VALID_BODY, "target_goal": "Hi"}
    resp = api_client.post("/api/v1/profiles", json=body)
    assert resp.status_code == 422


def test_get_profile_success(api_client: TestClient) -> None:
    create = api_client.post("/api/v1/profiles", json=_VALID_BODY)
    assert create.status_code == 201
    profile_id = create.json()["id"]

    resp = api_client.get(f"/api/v1/profiles/{profile_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == profile_id


def test_get_profile_not_found_wrong_id(api_client: TestClient) -> None:
    """Non-existent profile_id returns 404."""
    resp = api_client.get("/api/v1/profiles/nonexistent-id-000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] in ("RESOURCE_NOT_FOUND", "PROFILE_NOT_FOUND")


def test_get_profile_id_mismatch(api_client: TestClient) -> None:
    """Path id not matching stored profile returns 404."""
    api_client.post("/api/v1/profiles", json=_VALID_BODY)
    resp = api_client.get("/api/v1/profiles/wrong-id-xyz")
    assert resp.status_code == 404

