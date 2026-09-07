"""Infrastructure adapter: SqliteVectorStore.

Provides persistent vector similarity search using SQLite storage and
in-process cosine similarity calculation with deterministic tie-breaking.
"""

from __future__ import annotations

import math

from sqlalchemy.orm import Session

from roadmap.application.ports.vector_store import VectorEntry, VectorStore
from roadmap.domain.entities.knowledge import RetrievalFilter, RetrievalResult
from roadmap.storage.models.knowledge_model import (
    EmbeddingRecordModel,
    KnowledgeChunkModel,
)


class SqliteVectorStore(VectorStore):
    """VectorStore backed by SQLite embedding records and in-process cosine search."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, entries: list[VectorEntry]) -> None:
        """Upsert vector entries is handled at the repository layer, but supported here directly."""
        pass  # Embeddings and chunks are persisted via SqliteKnowledgeRepository

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievalResult]:
        """
        Search for nearest vectors by cosine similarity.
        Applies metadata filters and guarantees deterministic ranking and tie-breaking.
        """
        # Load active embeddings joined with chunk metadata
        query = (
            self._session.query(EmbeddingRecordModel, KnowledgeChunkModel)
            .join(KnowledgeChunkModel, KnowledgeChunkModel.id == EmbeddingRecordModel.chunk_id)
        )

        # Pre-filtering by provider, model, and evidence_ids if specified in filter
        if filters:
            if filters.provider:
                query = query.filter(EmbeddingRecordModel.provider == filters.provider)
            if filters.model:
                query = query.filter(EmbeddingRecordModel.model == filters.model)
            if filters.evidence_ids:
                query = query.filter(EmbeddingRecordModel.evidence_id.in_(filters.evidence_ids))

        rows = query.all()
        if not rows:
            return []

        q_norm = math.sqrt(sum(v * v for v in query_vector))
        if q_norm < 1e-9:
            return []

        scored_candidates: list[tuple[float, str, int, RetrievalResult]] = []
        min_threshold = filters.min_similarity if (filters and filters.min_similarity is not None) else -1.0

        for emb_model, chunk_model in rows:
            vec = emb_model.vector_list
            if len(vec) != len(query_vector):
                continue  # Skip incompatible dimensions

            # Dot product
            dot = sum(a * b for a, b in zip(query_vector, vec, strict=True))
            v_norm = math.sqrt(sum(x * x for x in vec))
            if v_norm < 1e-9:
                continue

            similarity = dot / (q_norm * v_norm)

            if similarity < min_threshold:
                continue

            chunk_meta = chunk_model.metadata_dict

            # Apply post-filters on metadata
            if filters:
                if filters.skill_names:
                    item_skills = [s.lower() for s in chunk_meta.get("associated_skills", [])]
                    match = any(req.lower() in item_skills for req in filters.skill_names)
                    if not match:
                        continue

                if filters.domain:
                    item_domain = chunk_meta.get("domain", "").lower()
                    if not item_domain.endswith(filters.domain.lower()):
                        continue

                if filters.source_types:
                    item_type = chunk_meta.get("source_type", "").lower()
                    if item_type not in [t.lower() for t in filters.source_types]:
                        continue

            res = RetrievalResult(
                chunk_id=chunk_model.id,
                document_id=chunk_model.document_id,
                evidence_id=chunk_model.evidence_id,
                similarity_score=round(float(similarity), 4),
                rank=1,  # updated after sort
                text=chunk_model.text,
                metadata=chunk_meta,
            )

            # Tuple for sorting: (-similarity, evidence_id, chunk_index, res)
            # Ensures highest similarity first, with deterministic tie-breaking
            scored_candidates.append((-similarity, chunk_model.evidence_id, chunk_model.chunk_index, res))

        # Sort deterministically
        scored_candidates.sort(key=lambda x: (x[0], x[1], x[2]))

        # Format final ranked results
        results: list[RetrievalResult] = []
        for rank, (_, _, _, res) in enumerate(scored_candidates[:top_k], start=1):
            res.rank = rank
            results.append(res)

        return results

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        self._session.query(EmbeddingRecordModel).filter(
            EmbeddingRecordModel.chunk_id.in_(chunk_ids)
        ).delete(synchronize_session=False)
        self._session.flush()

    def clear_for_document(self, document_id: str) -> None:
        chunk_ids = [
            r.id
            for r in self._session.query(KnowledgeChunkModel.id)
            .filter(KnowledgeChunkModel.document_id == document_id)
            .all()
        ]
        if chunk_ids:
            self.delete_by_chunk_ids(chunk_ids)

    def count(self) -> int:
        return self._session.query(EmbeddingRecordModel).count()
