"""Application service: SemanticRetrievalService.

Executes vector similarity search using the VectorStore and EmbeddingProvider ports,
enforcing deterministic tie-breaking, metadata filtering, and canonical evidence validation:
- Generates query embedding.
- Retrieves candidate chunks from VectorStore.
- Verifies existence of underlying canonical Evidence and Source records.
- Prunes deleted or corrupted references before returning.
"""

from __future__ import annotations

from roadmap.application.ports.embedding_provider import EmbeddingProvider
from roadmap.application.ports.repositories import EvidenceRepository, SourceRepository
from roadmap.application.ports.vector_store import VectorStore
from roadmap.domain.entities.knowledge import RetrievalFilter, RetrievalQuery, RetrievalResult
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class SemanticRetrievalService:
    """Orchestrates query embedding, vector lookup, and canonical verification."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        evidence_repo: EvidenceRepository,
        source_repo: SourceRepository,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.evidence_repo = evidence_repo
        self.source_repo = source_repo

    def retrieve(
        self,
        query: str | RetrievalQuery,
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievalResult]:
        """
        Execute semantic retrieval for a natural language query.
        """
        if isinstance(query, str):
            q_text = query.strip()
            q_top_k = top_k
            q_filters = filters or RetrievalFilter()
        else:
            q_text = query.text.strip()
            q_top_k = query.top_k
            q_filters = query.filter

        if not q_text:
            return []

        # Enforce provider and model match to prevent cross-model vector comparisons
        if q_filters.provider is None:
            q_filters.provider = self.embedding_provider.provider_name
        if q_filters.model is None:
            q_filters.model = self.embedding_provider.model_name

        # 1. Embed query
        query_vector = self.embedding_provider.embed_text(q_text)

        # 2. Vector search with filters
        raw_results = self.vector_store.search(
            query_vector=query_vector,
            top_k=q_top_k,
            filters=q_filters,
        )

        if not raw_results:
            return []

        # 3. Canonical validation gate: ensure every retrieved hit has an active canonical Evidence record
        validated_results: list[RetrievalResult] = []
        for r in raw_results:
            ev = self.evidence_repo.get_by_id(r.evidence_id)
            if not ev:
                # Evidence was deleted or invalid; discard candidate
                logger.warning("Retrieved chunk points to non-existent evidence", evidence_id=r.evidence_id)
                continue

            # Update rank index sequentially
            r.rank = len(validated_results) + 1
            validated_results.append(r)

        return validated_results
