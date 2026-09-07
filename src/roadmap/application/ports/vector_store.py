"""Application port: VectorStore protocol interface.

Defines the contract for persistent or in-memory vector storage and similarity search.
Infrastructure adapters (e.g. SqliteVectorStore, pgvector) implement this protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from roadmap.domain.entities.knowledge import RetrievalFilter, RetrievalResult


@dataclass(frozen=True)
class VectorEntry:
    """An indexed vector entry in the store."""

    chunk_id: str
    document_id: str
    evidence_id: str
    vector: list[float]
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """Port protocol for vector search index."""

    def upsert(self, entries: list[VectorEntry]) -> None:
        """Insert or overwrite vector entries."""
        ...

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievalResult]:
        """
        Search for nearest vector entries by cosine similarity.

        Returns:
            list[RetrievalResult] ordered deterministically by similarity score desc,
            with secondary tie-breaking by evidence_id asc, chunk_id asc.
        """
        ...

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        """Delete specific chunks from the index."""
        ...

    def clear_for_document(self, document_id: str) -> None:
        """Remove all vector entries associated with a document."""
        ...

    def count(self) -> int:
        """Return total number of vectors in the store."""
        ...
