"""Infrastructure adapter: GeminiEmbeddingProvider.

Integrates with Google Gemini's text-embedding-004 model via google-genai SDK.
"""

from __future__ import annotations

import math

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

from roadmap.application.ports.embedding_provider import (
    EmbeddingDimensionMismatchError,
    EmbeddingProvider,
    EmbeddingProviderError,
)
from roadmap.application.ports.llm_provider import MissingAPIKeyError
from roadmap.config.settings import settings
from roadmap.domain.value_objects.enums import FailureCategory
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_GEMINI_EMBEDDING_DIM = 768


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini text embedding provider."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        resolved_key = api_key or settings.gemini_api_key
        if not resolved_key or not resolved_key.strip():
            raise MissingAPIKeyError(provider="GeminiEmbedding", env_var="GEMINI_API_KEY")

        self.provider_name = "gemini"
        self.model_name = model or settings.embedding_model or DEFAULT_GEMINI_EMBEDDING_MODEL
        self.dimension = dimension or settings.embedding_dimension or DEFAULT_GEMINI_EMBEDDING_DIM
        self._client = genai.Client(api_key=resolved_key)

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        vectors = self.embed_batch([text])
        return vectors[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings using Gemini API."""
        if not texts:
            return []

        clean_texts = [t if t.strip() else " " for t in texts]

        try:
            config = types.EmbedContentConfig(output_dimensionality=self.dimension)
            response = self._client.models.embed_content(
                model=self.model_name,
                contents=clean_texts,
                config=config,
            )

            embeddings: list[list[float]] = []
            raw_embeddings = getattr(response, "embeddings", None)
            if not raw_embeddings:
                single_embedding = getattr(response, "embedding", None)
                if single_embedding:
                    raw_embeddings = [single_embedding]
                else:
                    raise EmbeddingProviderError("Gemini embedding API returned empty response")

            for item in raw_embeddings:
                vals = getattr(item, "values", None) or []
                float_vals = [float(v) for v in vals]

                if len(float_vals) != self.dimension:
                    raise EmbeddingDimensionMismatchError(
                        f"Expected vector dimension {self.dimension}, got {len(float_vals)} from Gemini"
                    )

                # Ensure unit normalization
                norm = math.sqrt(sum(v * v for v in float_vals))
                if norm > 1e-9:
                    float_vals = [v / norm for v in float_vals]

                embeddings.append(float_vals)

            return embeddings

        except ClientError as exc:
            logger.error("Gemini embedding client error", error=str(exc))
            err = EmbeddingProviderError(f"Gemini embedding client error: {exc}")
            err.failure_category = FailureCategory.INVALID_REQUEST
            raise err from exc
        except ServerError as exc:
            logger.error("Gemini embedding server error", error=str(exc))
            err = EmbeddingProviderError(f"Gemini embedding server error: {exc}")
            err.failure_category = FailureCategory.TRANSIENT_PROVIDER_ERROR
            raise err from exc
        except APIError as exc:
            logger.error("Gemini embedding API error", error=str(exc))
            err = EmbeddingProviderError(f"Gemini embedding API error: {exc}")
            err.failure_category = FailureCategory.UNKNOWN_PROVIDER_ERROR
            raise err from exc
        except Exception as exc:
            if isinstance(exc, (EmbeddingProviderError, MissingAPIKeyError)):
                raise
            logger.error("Unexpected error during Gemini embedding", error=str(exc))
            err = EmbeddingProviderError(f"Unexpected embedding failure: {exc}")
            err.failure_category = FailureCategory.UNKNOWN_PROVIDER_ERROR
            raise err from exc
