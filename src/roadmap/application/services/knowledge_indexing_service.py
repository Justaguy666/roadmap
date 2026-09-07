"""Application service: KnowledgeIndexingService.

Orchestrates the ingestion of canonical research evidence into searchable knowledge documents:
1. Scans canonical Evidence records and their parent Sources.
2. Derives KnowledgeDocuments with SHA-256 idempotency check.
3. Deterministically chunks content using KnowledgeChunker.
4. Generates embeddings via EmbeddingProvider port.
5. Performs safe transactional state transition (PENDING -> INDEXING -> READY).
6. Handles re-indexing: invalidates stale chunks and embeddings when content hash changes.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from roadmap.application.ports.embedding_provider import EmbeddingProvider
from roadmap.application.ports.repositories import EvidenceRepository, KnowledgeRepository, SourceRepository
from roadmap.domain.entities.knowledge import (
    DocumentStatus,
    EmbeddingRecord,
    KnowledgeDocument,
)
from roadmap.domain.entities.source import Evidence, Source
from roadmap.domain.services.knowledge_chunker import KnowledgeChunker
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)


class KnowledgeIndexingService:
    """Orchestrates indexing of canonical evidence into vector-embedded chunks."""

    def __init__(
        self,
        evidence_repo: EvidenceRepository,
        source_repo: SourceRepository,
        knowledge_repo: KnowledgeRepository,
        embedding_provider: EmbeddingProvider,
        chunker: KnowledgeChunker | None = None,
    ) -> None:
        self.evidence_repo = evidence_repo
        self.source_repo = source_repo
        self.knowledge_repo = knowledge_repo
        self.embedding_provider = embedding_provider
        self.chunker = chunker or KnowledgeChunker()

    def index_all_evidence(self, force: bool = False) -> dict[str, int]:
        """
        Scan all canonical evidence in the database and index unindexed or changed records.

        Returns:
            Dict summary of operations: {"documents": int, "chunks": int, "embeddings": int}
        """
        evidence_list = self.evidence_repo.list_all(limit=5000)
        all_sources = self.source_repo.list_all(limit=5000)
        source_map = {s.id: s for s in all_sources}

        docs_indexed = 0
        chunks_created = 0
        embeddings_generated = 0

        for ev in evidence_list:
            source = source_map.get(ev.source_id)
            status = self.index_single_evidence(ev, source, force=force)
            if status.get("indexed", False):
                docs_indexed += 1
                chunks_created += status.get("chunks", 0)
                embeddings_generated += status.get("embeddings", 0)

        logger.info(
            "Knowledge indexing completed",
            documents=docs_indexed,
            chunks=chunks_created,
            embeddings=embeddings_generated,
        )
        return {
            "documents": docs_indexed,
            "chunks": chunks_created,
            "embeddings": embeddings_generated,
        }

    def index_single_evidence(
        self,
        evidence: Evidence,
        source: Source | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Index or re-index a single evidence item.
        Idempotent: if content_hash matches and document is READY, skips re-computation unless force=True.
        """
        content = evidence.extracted_claim.strip()
        if not content:
            return {"indexed": False, "reason": "empty_content"}

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        existing_doc = self.knowledge_repo.get_document_by_evidence_id(evidence.id)
        same_identity = (
            existing_doc is not None
            and existing_doc.metadata.get("embedding_provider") == self.embedding_provider.provider_name
            and existing_doc.metadata.get("embedding_model") == self.embedding_provider.model_name
            and existing_doc.metadata.get("embedding_dimension") == self.embedding_provider.dimension
            and existing_doc.metadata.get("embedding_version") == "v1"
        )
        if (
            existing_doc
            and not force
            and existing_doc.content_hash == content_hash
            and existing_doc.status == DocumentStatus.READY
            and same_identity
        ):
            return {"indexed": False, "reason": "already_indexed_and_unchanged"}

        # Metadata to attach to document and propagate to chunks
        metadata: dict[str, Any] = {
            "evidence_id": evidence.id,
            "source_id": evidence.source_id,
            "associated_skills": evidence.associated_skill_names,
            "confidence": evidence.confidence,
            "relevance": evidence.relevance,
            "embedding_provider": self.embedding_provider.provider_name,
            "embedding_model": self.embedding_provider.model_name,
            "embedding_dimension": self.embedding_provider.dimension,
            "embedding_version": "v1",
        }
        if source:
            metadata["source_url"] = source.url
            metadata["source_title"] = source.title
            metadata["domain"] = source.domain
            metadata["source_type"] = source.source_type.value
            metadata["is_authoritative"] = source.is_authoritative
            metadata["publisher"] = source.publisher

        doc_id = existing_doc.id if existing_doc else new_id()
        doc = KnowledgeDocument(
            id=doc_id,
            evidence_id=evidence.id,
            source_id=evidence.source_id,
            title=source.title if source else f"Evidence {evidence.id[:8]}",
            content=content,
            content_hash=content_hash,
            status=DocumentStatus.INDEXING,
            chunk_count=0,
            metadata=metadata,
            created_at=existing_doc.created_at if existing_doc else datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Invalidate old chunks if re-indexing
        if existing_doc:
            self.knowledge_repo.delete_document(existing_doc.id)

        self.knowledge_repo.save_document(doc)

        try:
            # 1. Chunk document
            chunks = self.chunker.chunk_document(doc)
            if not chunks:
                doc.status = DocumentStatus.FAILED
                self.knowledge_repo.save_document(doc)
                return {"indexed": False, "reason": "no_chunks_produced"}

            self.knowledge_repo.save_chunks(chunks)

            # 2. Batch embed chunks
            chunk_texts = [c.text for c in chunks]
            vectors = self.embedding_provider.embed_batch(chunk_texts)

            # 3. Create embedding records
            now = datetime.now(UTC)
            embeddings: list[EmbeddingRecord] = []
            for chunk, vec in zip(chunks, vectors, strict=True):
                embeddings.append(
                    EmbeddingRecord(
                        id=new_id(),
                        chunk_id=chunk.id,
                        evidence_id=evidence.id,
                        provider=self.embedding_provider.provider_name,
                        model=self.embedding_provider.model_name,
                        dimension=self.embedding_provider.dimension,
                        embedding_version="v1",
                        vector=vec,
                        created_at=now,
                    )
                )

            self.knowledge_repo.save_embeddings(embeddings)

            # 4. Mark document READY
            doc.status = DocumentStatus.READY
            doc.chunk_count = len(chunks)
            doc.updated_at = datetime.now(UTC)
            self.knowledge_repo.save_document(doc)

            return {
                "indexed": True,
                "document_id": doc.id,
                "chunks": len(chunks),
                "embeddings": len(embeddings),
            }

        except Exception as exc:
            logger.error("Failed to index knowledge document", error=str(exc), evidence_id=evidence.id)
            doc.status = DocumentStatus.FAILED
            self.knowledge_repo.save_document(doc)
            raise
