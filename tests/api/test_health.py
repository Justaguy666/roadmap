"""Tests: GET /health and GET /health/readiness."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from roadmap.api.dependencies import (
    get_db_session,
    get_embedding_provider,
    get_llm_provider,
)
from roadmap.api.main import app
from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider


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


def test_readiness_does_not_invoke_external_providers(api_client: TestClient) -> None:
    """
    Readiness must strictly check only DB connectivity (SELECT 1).
    It must NOT invoke LLM, embedding, or search providers.
    """
    fake_llm = FakeLLMProvider()
    fake_emb = FakeEmbeddingProvider()

    # Wrap methods with spies
    llm_spy = MagicMock(wraps=fake_llm.complete)
    fake_llm.complete = llm_spy  # type: ignore[assignment]

    emb_spy = MagicMock(wraps=fake_emb.embed_text)
    emb_batch_spy = MagicMock(wraps=fake_emb.embed_batch)
    fake_emb.embed_text = emb_spy  # type: ignore[assignment]
    fake_emb.embed_batch = emb_batch_spy  # type: ignore[assignment]

    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    app.dependency_overrides[get_embedding_provider] = lambda: fake_emb

    try:
        resp = api_client.get("/health/readiness")
        assert resp.status_code == 200

        # Assert zero provider calls
        assert llm_spy.call_count == 0, f"LLM was invoked {llm_spy.call_count} times during readiness"
        assert len(fake_llm.calls) == 0, "FakeLLMProvider calls list is not empty"
        assert emb_spy.call_count == 0, f"Embedding provider was invoked {emb_spy.call_count} times"
        assert emb_batch_spy.call_count == 0, f"Embedding batch was invoked {emb_batch_spy.call_count} times"
    finally:
        # Revert overrides to conftest standard
        app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider()
        app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()


def test_readiness_error_sanitization_no_sql_disclosure(api_client: TestClient) -> None:
    """
    When database execution fails, readiness probe must:
    1. Return status: not_ready, database: unavailable
    2. Return HTTP 503
    3. NOT disclose raw SQL, driver exceptions, or internal table names in the response body.
    """
    # Mock a broken session that raises OperationalError with raw SQL details
    broken_session = MagicMock()
    secret_table_msg = "no such table: secret_internal_user_data_xyz123"
    broken_session.execute.side_effect = OperationalError(
        statement="SELECT * FROM secret_internal_user_data_xyz123",
        params={},
        orig=Exception(secret_table_msg),
    )

    def override_broken_session():
        yield broken_session

    app.dependency_overrides[get_db_session] = override_broken_session

    try:
        resp = api_client.get("/health/readiness")
        assert resp.status_code == 503
        data = resp.json()

        assert data["status"] == "not_ready"
        assert data["database"] == "unavailable"

        # Explicitly verify NO internal SQL or exception text leaked
        response_text = resp.text
        assert "secret_internal_user_data_xyz123" not in response_text
        assert "OperationalError" not in response_text
        assert "SELECT" not in response_text
        assert "error:" not in response_text
    finally:
        # Fixture in conftest will restore standard override
        pass
