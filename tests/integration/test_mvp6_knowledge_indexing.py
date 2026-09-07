"""Integration tests for MVP-6 Knowledge Indexing Pipeline."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from roadmap.application.services.knowledge_indexing_service import KnowledgeIndexingService
from roadmap.domain.services.knowledge_chunker import KnowledgeChunker
from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from roadmap.storage.models.knowledge_model import (
    EmbeddingRecordModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)
from roadmap.storage.models.progress_model import SourceModel
from roadmap.storage.models.research_model import EvidenceModel
from roadmap.storage.repositories.knowledge_repository import SqliteKnowledgeRepository
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteSourceRepository,
)


def _seed_sample_evidence(session) -> tuple[SourceModel, list[EvidenceModel]]:
    now = datetime.now(UTC)
    source = SourceModel(
        id="src-game-dev-1",
        url="https://jobs.example.com/engine-programmer",
        title="Engine Programmer Requirements",
        source_type="job_posting",
        publisher="GameStudio",
        domain="example.com",
        retrieved_at=now,
        reliability_score=0.9,
    )
    session.add(source)
    session.flush()

    ev1 = EvidenceModel(
        id="ev-cpp-memory",
        source_id=source.id,
        extracted_claim="Candidates must have deep understanding of C++ memory models, pointers, and RAII.",
        relevance=0.95,
        confidence=0.9,
        associated_skill_names_json=json.dumps(["C++", "Memory Management"]),
        created_at=now,
    )
    ev2 = EvidenceModel(
        id="ev-data-oriented",
        source_id=source.id,
        extracted_claim="Modern game development emphasizes cache locality, ECS architecture, and data-oriented design.",
        relevance=0.88,
        confidence=0.85,
        associated_skill_names_json=json.dumps(["Data-Oriented Design", "ECS"]),
        created_at=now,
    )
    session.add_all([ev1, ev2])
    session.flush()
    return source, [ev1, ev2]


class TestKnowledgeIndexingIntegration:
    def test_full_indexing_lifecycle(self, db_session) -> None:
        source, evidence_list = _seed_sample_evidence(db_session)

        evidence_repo = SqliteEvidenceRepository(db_session)
        source_repo = SqliteSourceRepository(db_session)
        knowledge_repo = SqliteKnowledgeRepository(db_session)
        embedding_provider = FakeEmbeddingProvider(dimension=768)
        chunker = KnowledgeChunker(chunk_size=200, chunk_overlap=30)

        indexing_service = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=embedding_provider,
            chunker=chunker,
        )

        # Initial indexing run
        summary = indexing_service.index_all_evidence()
        assert summary["documents"] == 2
        assert summary["chunks"] >= 2
        assert summary["embeddings"] >= 2

        # Verify DB records
        docs = db_session.query(KnowledgeDocumentModel).all()
        assert len(docs) == 2
        for d in docs:
            assert d.status == "READY"
            assert d.chunk_count >= 1

        chunks = db_session.query(KnowledgeChunkModel).all()
        assert len(chunks) == summary["chunks"]

        embeddings = db_session.query(EmbeddingRecordModel).all()
        assert len(embeddings) == summary["embeddings"]

        # 2nd run: Idempotency (hashes match, nothing re-indexed)
        idempotent_summary = indexing_service.index_all_evidence()
        assert idempotent_summary["documents"] == 0
        assert idempotent_summary["chunks"] == 0
        assert idempotent_summary["embeddings"] == 0

        # Force re-indexing
        force_summary = indexing_service.index_all_evidence(force=True)
        assert force_summary["documents"] == 2
        assert force_summary["chunks"] >= 2
        assert force_summary["embeddings"] >= 2

    def test_content_mutation_triggers_reindexing(self, db_session) -> None:
        source, evidence_list = _seed_sample_evidence(db_session)

        evidence_repo = SqliteEvidenceRepository(db_session)
        source_repo = SqliteSourceRepository(db_session)
        knowledge_repo = SqliteKnowledgeRepository(db_session)
        embedding_provider = FakeEmbeddingProvider(dimension=768)
        chunker = KnowledgeChunker(chunk_size=200, chunk_overlap=30)

        indexing_service = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=embedding_provider,
            chunker=chunker,
        )

        indexing_service.index_all_evidence()

        # Mutate the extracted claim of ev-cpp-memory
        ev1 = db_session.query(EvidenceModel).filter_by(id="ev-cpp-memory").one()
        ev1.extracted_claim = "Updated claim: C++20 ranges and concepts are now strictly required."
        db_session.flush()

        # Run indexing without force: only the mutated evidence should be updated
        delta_summary = indexing_service.index_all_evidence(force=False)
        assert delta_summary["documents"] == 1
        assert delta_summary["chunks"] >= 1
        assert delta_summary["embeddings"] >= 1

        updated_doc = db_session.query(KnowledgeDocumentModel).filter_by(evidence_id="ev-cpp-memory").one()
        assert "Updated claim" in updated_doc.content
