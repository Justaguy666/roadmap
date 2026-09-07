"""SQLAlchemy implementation of KnowledgeRepository."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from roadmap.domain.entities.knowledge import (
    DocumentStatus,
    EmbeddingRecord,
    KnowledgeChunk,
    KnowledgeDocument,
)
from roadmap.storage.models.knowledge_model import (
    EmbeddingRecordModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)


class SqliteKnowledgeRepository:
    """Repository for Knowledge Documents, Chunks, and Embedding Records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Documents ─────────────────────────────────────────────────────────────

    def save_document(self, document: KnowledgeDocument) -> None:
        existing = self._session.get(KnowledgeDocumentModel, document.id)
        if existing:
            existing.title = document.title
            existing.content = document.content
            existing.content_hash = document.content_hash
            existing.status = document.status.value
            existing.chunk_count = document.chunk_count
            existing.metadata_json = json.dumps(document.metadata)
            existing.updated_at = document.updated_at
        else:
            model = KnowledgeDocumentModel(
                id=document.id,
                evidence_id=document.evidence_id,
                source_id=document.source_id,
                title=document.title,
                content=document.content,
                content_hash=document.content_hash,
                status=document.status.value,
                chunk_count=document.chunk_count,
                metadata_json=json.dumps(document.metadata),
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            self._session.add(model)
        self._session.flush()

    def get_document_by_id(self, document_id: str) -> KnowledgeDocument | None:
        model = self._session.get(KnowledgeDocumentModel, document_id)
        return self._to_document_entity(model) if model else None

    def get_document_by_evidence_id(self, evidence_id: str) -> KnowledgeDocument | None:
        model = (
            self._session.query(KnowledgeDocumentModel)
            .filter(KnowledgeDocumentModel.evidence_id == evidence_id)
            .first()
        )
        return self._to_document_entity(model) if model else None

    def list_all_documents(self, limit: int = 1000) -> list[KnowledgeDocument]:
        models = self._session.query(KnowledgeDocumentModel).limit(limit).all()
        return [self._to_document_entity(m) for m in models]

    def delete_document(self, document_id: str) -> None:
        model = self._session.get(KnowledgeDocumentModel, document_id)
        if model:
            # Delete child chunks and embeddings explicitly if cascade not automatic
            self._session.query(EmbeddingRecordModel).filter(
                EmbeddingRecordModel.chunk_id.in_(
                    self._session.query(KnowledgeChunkModel.id).filter(
                        KnowledgeChunkModel.document_id == document_id
                    )
                )
            ).delete(synchronize_session=False)
            self._session.query(KnowledgeChunkModel).filter(
                KnowledgeChunkModel.document_id == document_id
            ).delete(synchronize_session=False)
            self._session.delete(model)
            self._session.flush()

    # ── Chunks ────────────────────────────────────────────────────────────────

    def save_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        for chunk in chunks:
            existing = self._session.get(KnowledgeChunkModel, chunk.id)
            if existing:
                existing.text = chunk.text
                existing.content_hash = chunk.content_hash
                existing.chunk_index = chunk.chunk_index
                existing.metadata_json = json.dumps(chunk.metadata)
            else:
                model = KnowledgeChunkModel(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    evidence_id=chunk.evidence_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    content_hash=chunk.content_hash,
                    metadata_json=json.dumps(chunk.metadata),
                    created_at=chunk.created_at,
                )
                self._session.add(model)
        self._session.flush()

    def get_chunk_by_id(self, chunk_id: str) -> KnowledgeChunk | None:
        model = self._session.get(KnowledgeChunkModel, chunk_id)
        return self._to_chunk_entity(model) if model else None

    def list_chunks_for_document(self, document_id: str) -> list[KnowledgeChunk]:
        models = (
            self._session.query(KnowledgeChunkModel)
            .filter(KnowledgeChunkModel.document_id == document_id)
            .order_by(KnowledgeChunkModel.chunk_index.asc())
            .all()
        )
        return [self._to_chunk_entity(m) for m in models]

    def count_chunks(self) -> int:
        return self._session.query(KnowledgeChunkModel).count()

    def count_documents(self) -> int:
        return self._session.query(KnowledgeDocumentModel).count()

    # ── Embeddings ────────────────────────────────────────────────────────────

    def save_embeddings(self, records: list[EmbeddingRecord]) -> None:
        for rec in records:
            existing = self._session.get(EmbeddingRecordModel, rec.id)
            if existing:
                existing.provider = rec.provider
                existing.model = rec.model
                existing.dimension = rec.dimension
                existing.embedding_version = rec.embedding_version
                existing.vector_json = json.dumps(rec.vector)
            else:
                model = EmbeddingRecordModel(
                    id=rec.id,
                    chunk_id=rec.chunk_id,
                    evidence_id=rec.evidence_id,
                    provider=rec.provider,
                    model=rec.model,
                    dimension=rec.dimension,
                    embedding_version=rec.embedding_version,
                    vector_json=json.dumps(rec.vector),
                    created_at=rec.created_at,
                )
                self._session.add(model)
        self._session.flush()

    def get_embedding_by_chunk_id(self, chunk_id: str) -> EmbeddingRecord | None:
        model = (
            self._session.query(EmbeddingRecordModel)
            .filter(EmbeddingRecordModel.chunk_id == chunk_id)
            .first()
        )
        return self._to_embedding_entity(model) if model else None

    def list_all_embeddings(self, limit: int = 5000) -> list[EmbeddingRecord]:
        models = self._session.query(EmbeddingRecordModel).limit(limit).all()
        return [self._to_embedding_entity(m) for m in models]

    def count_embeddings(self) -> int:
        return self._session.query(EmbeddingRecordModel).count()

    # ── Entity converters ─────────────────────────────────────────────────────

    def _to_document_entity(self, m: KnowledgeDocumentModel) -> KnowledgeDocument:
        return KnowledgeDocument(
            id=m.id,
            evidence_id=m.evidence_id,
            source_id=m.source_id,
            title=m.title,
            content=m.content,
            content_hash=m.content_hash,
            status=DocumentStatus(m.status),
            chunk_count=m.chunk_count,
            metadata=json.loads(m.metadata_json),
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def _to_chunk_entity(self, m: KnowledgeChunkModel) -> KnowledgeChunk:
        return KnowledgeChunk(
            id=m.id,
            document_id=m.document_id,
            evidence_id=m.evidence_id,
            chunk_index=m.chunk_index,
            text=m.text,
            content_hash=m.content_hash,
            metadata=json.loads(m.metadata_json),
            created_at=m.created_at,
        )

    def _to_embedding_entity(self, m: EmbeddingRecordModel) -> EmbeddingRecord:
        return EmbeddingRecord(
            id=m.id,
            chunk_id=m.chunk_id,
            evidence_id=m.evidence_id,
            provider=m.provider,
            model=m.model,
            dimension=m.dimension,
            embedding_version=m.embedding_version,
            vector=json.loads(m.vector_json),
            created_at=m.created_at,
        )
