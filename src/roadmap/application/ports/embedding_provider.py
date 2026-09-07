"""Application port: EmbeddingProvider protocol interface.

Defines the contract for vector embedding providers.
Infrastructure adapters (Fake, Gemini, OpenAI) implement this protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from roadmap.domain.value_objects.enums import FailureCategory


class EmbeddingProviderError(Exception):
    """Base exception for embedding generation failures."""

    failure_category: FailureCategory = FailureCategory.UNKNOWN_PROVIDER_ERROR


class EmbeddingDimensionMismatchError(EmbeddingProviderError):
    """Raised when an embedding vector length does not match configured dimension."""

    failure_category = FailureCategory.INVALID_REQUEST


@runtime_checkable
class EmbeddingProvider(Protocol):
    """
    Port protocol for embedding generation services.
    """

    provider_name: str
    model_name: str
    dimension: int

    def embed_text(self, text: str) -> list[float]:
        """
        Generate vector embedding for a single text chunk.

        Returns:
            list[float] of length == self.dimension.
        """
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate vector embeddings for a list of text chunks.

        Returns:
            list[list[float]] where each item has length == self.dimension.
        """
        ...
