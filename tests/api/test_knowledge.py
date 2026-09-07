"""Tests: Knowledge search endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

_PROFILE_BODY = {
    "name": "Knowledge User",
    "target_goal": "Become a machine learning engineer",
    "current_level": "missing",
    "study_hours_per_day": 2.0,
    "deadline_months": 12,
}


def _create_profile(client: TestClient) -> str:
    resp = client.post("/api/v1/profiles", json=_PROFILE_BODY)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_knowledge_search_empty_index(api_client: TestClient) -> None:
    """Knowledge search returns empty results when no documents are indexed."""
    pid = _create_profile(api_client)
    resp = api_client.get(
        f"/api/v1/profiles/{pid}/knowledge/search",
        params={"query": "Python programming"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Python programming"
    assert data["retrieved_count"] == 0
    assert data["results"] == []


def test_knowledge_search_no_profile(api_client: TestClient) -> None:
    resp = api_client.get(
        "/api/v1/profiles/nonexistent/knowledge/search",
        params={"query": "test query"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROFILE_NOT_FOUND"


def test_knowledge_search_missing_query(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    resp = api_client.get(f"/api/v1/profiles/{pid}/knowledge/search")
    assert resp.status_code == 422


def test_knowledge_search_invalid_top_k(api_client: TestClient) -> None:
    pid = _create_profile(api_client)
    resp = api_client.get(
        f"/api/v1/profiles/{pid}/knowledge/search",
        params={"query": "test", "top_k": 0},  # invalid: must be >= 1
    )
    assert resp.status_code == 422


def test_knowledge_search_with_filters(api_client: TestClient) -> None:
    """Filters are accepted without error even if no results match."""
    pid = _create_profile(api_client)
    resp = api_client.get(
        f"/api/v1/profiles/{pid}/knowledge/search",
        params={
            "query": "deep learning",
            "top_k": 3,
            "skill_name": "PyTorch",
            "threshold": 0.5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["retrieved_count"] == 0


def test_knowledge_search_preserves_canonical_fields(api_client: TestClient) -> None:
    """Even with results, response must include evidence_id (provenance)."""
    pid = _create_profile(api_client)
    resp = api_client.get(
        f"/api/v1/profiles/{pid}/knowledge/search",
        params={"query": "neural networks"},
    )
    assert resp.status_code == 200
    # With no indexed data, results is empty — structural check on schema
    data = resp.json()
    assert "query" in data
    assert "retrieved_count" in data
    assert "results" in data
    # Each result item (if any) must have evidence_id
    for item in data["results"]:
        assert "evidence_id" in item

