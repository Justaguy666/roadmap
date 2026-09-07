"""Infrastructure adapter: FakeEmbeddingProvider.

Provides 100% deterministic, offline vector embeddings for testing and local development.
Vector generation uses SHA-256 hash projections normalized to unit hypersphere:
- Identical text + model -> identical vector
- Vector magnitude is 1.0 (L2 normalized)
- Orthogonal/distinct inputs produce low similarity scores
"""

from __future__ import annotations

import hashlib
import math

from roadmap.application.ports.embedding_provider import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic offline embedding provider."""

    def __init__(
        self,
        dimension: int = 768,
        model_name: str = "fake-embedding-v1",
    ) -> None:
        self.provider_name = "fake"
        self.model_name = model_name
        self.dimension = dimension

    def embed_text(self, text: str) -> list[float]:
        """Generate a deterministic unit vector from text content."""
        return self._generate_vector(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic unit vectors for a list of texts."""
        return [self._generate_vector(t) for t in texts]

    def _generate_vector(self, text: str) -> list[float]:
        """Generate deterministic normalized vector of length `dimension`."""
        if not text.strip():
            # Return zero vector if empty
            return [0.0] * self.dimension

        # Derive pseudorandom floating values from consecutive SHA-256 blocks
        vals: list[float] = []
        seed = f"{self.model_name}:{text}"
        block_idx = 0

        while len(vals) < self.dimension:
            block_seed = f"{seed}:{block_idx}"
            h = hashlib.sha256(block_seed.encode("utf-8")).digest()
            for i in range(0, len(h), 4):
                if len(vals) >= self.dimension:
                    break
                # Convert 4 bytes to an integer and map to [-1.0, 1.0]
                int_val = int.from_bytes(h[i : i + 4], byteorder="big", signed=True)
                vals.append(float(int_val) / 2147483648.0)
            block_idx += 1

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vals))
        return (
            [round(v / norm, 6) for v in vals]
            if norm > 1e-9
            else [0.0] * self.dimension
        )
