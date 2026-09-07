"""Unit tests for embedding providers (Fake and Gemini)."""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from roadmap.application.ports.embedding_provider import (
    EmbeddingDimensionMismatchError,
)
from roadmap.application.ports.llm_provider import MissingAPIKeyError
from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from roadmap.infrastructure.embeddings.gemini_embedding_provider import GeminiEmbeddingProvider


class TestFakeEmbeddingProvider:
    def test_provider_properties(self) -> None:
        provider = FakeEmbeddingProvider(dimension=768, model_name="gemini-embedding-001")
        assert provider.provider_name == "fake"
        assert provider.model_name == "gemini-embedding-001"
        assert provider.dimension == 768

    def test_vector_dimension(self) -> None:
        provider = FakeEmbeddingProvider(dimension=256)
        vec = provider.embed_text("Test embedding vector length")
        assert len(vec) == 256

    def test_vector_unit_normalized(self) -> None:
        provider = FakeEmbeddingProvider(dimension=128)
        vec = provider.embed_text("Normalize this vector")
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-5

    def test_deterministic_reproducibility(self) -> None:
        provider = FakeEmbeddingProvider(dimension=768)
        text = "Deterministic vector generation"
        vec1 = provider.embed_text(text)
        vec2 = provider.embed_text(text)
        assert vec1 == vec2

    def test_different_texts_produce_different_vectors(self) -> None:
        provider = FakeEmbeddingProvider(dimension=768)
        vec1 = provider.embed_text("Text sample A")
        vec2 = provider.embed_text("Text sample B")
        assert vec1 != vec2

    def test_batch_matches_single(self) -> None:
        provider = FakeEmbeddingProvider(dimension=64)
        texts = ["Text one", "Text two", "Text three"]
        batch = provider.embed_batch(texts)
        assert len(batch) == 3
        for text, vec in zip(texts, batch, strict=True):
            assert provider.embed_text(text) == vec

    def test_empty_batch(self) -> None:
        provider = FakeEmbeddingProvider(dimension=64)
        assert provider.embed_batch([]) == []


class TestGeminiEmbeddingProvider:
    def test_gemini_missing_api_key_raises_error(self) -> None:
        with (
            patch("roadmap.infrastructure.embeddings.gemini_embedding_provider.settings.gemini_api_key", ""),
            pytest.raises(MissingAPIKeyError),
        ):
            GeminiEmbeddingProvider(api_key="")

    @patch("roadmap.infrastructure.embeddings.gemini_embedding_provider.genai.Client")
    def test_gemini_embed_text_dimension_mismatch(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_item = MagicMock()
        # Return dimension 512 when expecting 768
        mock_item.values = [0.1] * 512
        mock_client.models.embed_content.return_value.embeddings = [mock_item]

        provider = GeminiEmbeddingProvider(api_key="fake-key", dimension=768)

        with pytest.raises(EmbeddingDimensionMismatchError, match="Expected vector dimension 768, got 512"):
            provider.embed_text("hello world")

    @patch("roadmap.infrastructure.embeddings.gemini_embedding_provider.genai.Client")
    def test_gemini_embed_batch_success(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_emb1 = MagicMock()
        mock_emb1.values = [0.1] * 768
        mock_emb2 = MagicMock()
        mock_emb2.values = [0.2] * 768
        mock_client.models.embed_content.return_value.embeddings = [mock_emb1, mock_emb2]

        provider = GeminiEmbeddingProvider(api_key="fake-key", dimension=768)
        results = provider.embed_batch(["alpha", "beta"])

        assert len(results) == 2
        assert len(results[0]) == 768
        assert len(results[1]) == 768
        norm1 = math.sqrt(sum(v * v for v in results[0]))
        assert abs(norm1 - 1.0) < 1e-4
