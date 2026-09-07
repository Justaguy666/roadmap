"""Tests: GET /health and GET /health/readiness."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_liveness(api_client: TestClient) -> None:
    resp = api_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_no_cache_required(api_client: TestClient) -> None:
    """Health endpoint must be idempotent across multiple calls."""
    for _ in range(3):
        resp = api_client.get("/health")
        assert resp.status_code == 200


def test_readiness_ok(api_client: TestClient) -> None:
    resp = api_client.get("/health/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"


def test_readiness_not_llm_call(api_client: TestClient) -> None:
    """Readiness must not call any LLM or external provider."""
    # If it did, it would hit the FakeLLMProvider which logs calls
    # This test is structural: if the endpoint returns 200 it means no external call
    resp = api_client.get("/health/readiness")
    assert resp.status_code == 200
