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
    assert resp.json()["error"]["code"] in ("RESOURCE_NOT_FOUND", "PROFILE_NOT_FOUND")


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


def test_knowledge_search_embedding_provider_failure_returns_503(api_client: TestClient) -> None:
    """
    Regression test: When embedding provider fails, API must return HTTP 503 PROVIDER_ERROR.
    It must NOT silently fall back to FakeEmbeddingProvider.
    """
    from unittest.mock import MagicMock

    from roadmap.api.dependencies import get_embedding_provider
    from roadmap.api.main import app
    from roadmap.application.ports.embedding_provider import EmbeddingProviderError

    pid = _create_profile(api_client)

    broken_emb = MagicMock()
    broken_emb.embed_text.side_effect = EmbeddingProviderError(
        "Gemini API rate limit exceeded / upstream 503",
    )

    app.dependency_overrides[get_embedding_provider] = lambda: broken_emb

    try:
        resp = api_client.get(
            f"/api/v1/profiles/{pid}/knowledge/search",
            params={"query": "neural networks"},
        )
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "PROVIDER_ERROR"
        assert data["error"]["message"] == "Embedding provider is unavailable"
    finally:
        # Restore standard fake provider override for subsequent tests
        from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
        app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()


def test_knowledge_search_missing_api_key_returns_503(api_client: TestClient) -> None:
    """
    Regression test: When embedding API key is unconfigured in production mode,
    API must return HTTP 503 PROVIDER_ERROR rather than silently falling back.
    """
    from roadmap.api.dependencies import get_embedding_provider
    from roadmap.api.main import app
    from roadmap.application.ports.llm_provider import MissingAPIKeyError

    pid = _create_profile(api_client)

    def failing_emb_factory():
        raise MissingAPIKeyError(provider="GeminiEmbedding", env_var="GEMINI_API_KEY")

    app.dependency_overrides[get_embedding_provider] = failing_emb_factory

    try:
        resp = api_client.get(
            f"/api/v1/profiles/{pid}/knowledge/search",
            params={"query": "neural networks"},
        )
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "PROVIDER_ERROR"
        assert "GEMINI_API_KEY" in data["error"]["message"] or "GeminiEmbedding" in data["error"]["message"]
    finally:
        from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
        app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()


def test_production_embedding_provider_does_not_silently_fallback(
    api_client: TestClient, monkeypatch
) -> None:
    """
    Prove that in production configuration (embedding_provider='gemini' without API key),
    removing the test override causes an explicit 503 PROVIDER_ERROR failure,
    confirming the system does NOT silently switch to fake.
    """
    from roadmap.api.dependencies import get_embedding_provider
    from roadmap.api.main import app
    from roadmap.config.settings import settings

    pid = _create_profile(api_client)

    # Set production config with missing API key
    monkeypatch.setattr(settings, "embedding_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    # Remove test override to let production dependency execute
    app.dependency_overrides.pop(get_embedding_provider, None)

    try:
        resp = api_client.get(
            f"/api/v1/profiles/{pid}/knowledge/search",
            params={"query": "neural networks"},
        )
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "PROVIDER_ERROR"
    finally:
        from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
        app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()



