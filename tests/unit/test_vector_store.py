"""Unit tests for SqliteVectorStore and vector search operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from roadmap.domain.entities.knowledge import RetrievalFilter
from roadmap.infrastructure.vector_store.sqlite_vector_store import SqliteVectorStore
from roadmap.storage.models.knowledge_model import (
    EmbeddingRecordModel,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)
from roadmap.storage.models.progress_model import SourceModel
from roadmap.storage.models.research_model import EvidenceModel


def _seed_chunk_and_embedding(
    session,
    chunk_id: str,
    evidence_id: str,
    doc_id: str,
    chunk_index: int,
    text: str,
    vector: list[float],
    metadata: dict | None = None,
) -> None:
    now = datetime.now(UTC)

    # Ensure source exists
    src = session.query(SourceModel).filter_by(id=f"src-{evidence_id}").first()
    if not src:
        src = SourceModel(
            id=f"src-{evidence_id}",
            url=f"https://example.com/{evidence_id}",
            title="Example Source",
            source_type="documentation",
            reliability_score=0.9,
            retrieved_at=now,
        )
        session.add(src)
        session.flush()

    # Ensure evidence exists
    ev = session.query(EvidenceModel).filter_by(id=evidence_id).first()
    if not ev:
        ev = EvidenceModel(
            id=evidence_id,
            source_id=src.id,
            extracted_claim=text,
            relevance=0.8,
            confidence=0.8,
            associated_skill_names_json=json.dumps(metadata.get("associated_skills", []) if metadata else []),
            created_at=now,
        )
        session.add(ev)
        session.flush()

    doc = session.query(KnowledgeDocumentModel).filter_by(id=doc_id).first()
    if not doc:
        doc = KnowledgeDocumentModel(
            id=doc_id,
            evidence_id=evidence_id,
            source_id=src.id,
            title="Test Doc",
            content=text,
            content_hash="hash",
            status="READY",
            chunk_count=1,
            metadata_json="{}",
            created_at=now,
            updated_at=now,
        )
        session.add(doc)
        session.flush()

    chunk = KnowledgeChunkModel(
        id=chunk_id,
        document_id=doc_id,
        evidence_id=evidence_id,
        chunk_index=chunk_index,
        text=text,
        content_hash="chkhash",
        metadata_json=json.dumps(metadata or {}),
        created_at=now,
    )
    session.add(chunk)
    session.flush()

    emb = EmbeddingRecordModel(
        id=f"emb-{chunk_id}",
        chunk_id=chunk_id,
        evidence_id=evidence_id,
        provider="fake",
        model="gemini-embedding-001",
        dimension=len(vector),
        embedding_version="v1",
        vector_json=json.dumps(vector),
        created_at=now,
    )
    session.add(emb)
    session.flush()


class TestSqliteVectorStore:
    def test_search_exact_match(self, db_session) -> None:
        store = SqliteVectorStore(db_session)
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]

        _seed_chunk_and_embedding(
            db_session,
            chunk_id="chk-1",
            evidence_id="ev-1",
            doc_id="doc-1",
            chunk_index=0,
            text="C++ text",
            vector=vec_a,
            metadata={"associated_skills": ["C++"]},
        )
        _seed_chunk_and_embedding(
            db_session,
            chunk_id="chk-2",
            evidence_id="ev-2",
            doc_id="doc-2",
            chunk_index=0,
            text="Python text",
            vector=vec_b,
            metadata={"associated_skills": ["Python"]},
        )

        results = store.search(query_vector=vec_a, top_k=2)
        assert len(results) == 2
        assert results[0].chunk_id == "chk-1"
        assert abs(results[0].similarity_score - 1.0) < 1e-4
        assert results[1].chunk_id == "chk-2"
        assert abs(results[1].similarity_score - 0.0) < 1e-4

    def test_threshold_filtering(self, db_session) -> None:
        store = SqliteVectorStore(db_session)
        _seed_chunk_and_embedding(
            db_session, "chk-1", "ev-1", "doc-1", 0, "Match", [1.0, 0.0]
        )
        _seed_chunk_and_embedding(
            db_session, "chk-2", "ev-2", "doc-2", 0, "No Match", [0.0, 1.0]
        )

        filters = RetrievalFilter(min_similarity=0.5)
        results = store.search(query_vector=[1.0, 0.0], top_k=5, filters=filters)
        assert len(results) == 1
        assert results[0].chunk_id == "chk-1"

    def test_skill_filter(self, db_session) -> None:
        store = SqliteVectorStore(db_session)
        _seed_chunk_and_embedding(
            db_session,
            "chk-1",
            "ev-1",
            "doc-1",
            0,
            "Rust text",
            [1.0, 0.0],
            metadata={"associated_skills": ["Rust", "Systems"]},
        )
        _seed_chunk_and_embedding(
            db_session,
            "chk-2",
            "ev-2",
            "doc-2",
            0,
            "Python text",
            [1.0, 0.0],
            metadata={"associated_skills": ["Python", "Django"]},
        )

        filters = RetrievalFilter(skill_names=["Rust"])
        results = store.search(query_vector=[1.0, 0.0], top_k=5, filters=filters)
        assert len(results) == 1
        assert results[0].chunk_id == "chk-1"

    def test_domain_filter(self, db_session) -> None:
        store = SqliteVectorStore(db_session)
        _seed_chunk_and_embedding(
            db_session,
            "chk-1",
            "ev-1",
            "doc-1",
            0,
            "Larian job",
            [1.0, 0.0],
            metadata={"domain": "larian.com"},
        )
        _seed_chunk_and_embedding(
            db_session,
            "chk-2",
            "ev-2",
            "doc-2",
            0,
            "Reddit post",
            [1.0, 0.0],
            metadata={"domain": "reddit.com"},
        )

        filters = RetrievalFilter(domain="larian.com")
        results = store.search(query_vector=[1.0, 0.0], top_k=5, filters=filters)
        assert len(results) == 1
        assert results[0].chunk_id == "chk-1"

    def test_deterministic_tie_breaking(self, db_session) -> None:
        store = SqliteVectorStore(db_session)
        vec = [1.0, 0.0]
        _seed_chunk_and_embedding(
            db_session, "chk-b", "ev-z", "doc-z", 1, "Z", vec
        )
        _seed_chunk_and_embedding(
            db_session, "chk-a", "ev-a", "doc-a", 0, "A", vec
        )

        results = store.search(query_vector=vec, top_k=5)
        assert len(results) == 2
        # 'ev-a' before 'ev-z'
        assert results[0].chunk_id == "chk-a"
        assert results[1].chunk_id == "chk-b"

    def test_delete_by_chunk_ids(self, db_session) -> None:
        store = SqliteVectorStore(db_session)
        _seed_chunk_and_embedding(
            db_session, "chk-1", "ev-1", "doc-1", 0, "One", [1.0, 0.0]
        )
        _seed_chunk_and_embedding(
            db_session, "chk-2", "ev-2", "doc-2", 0, "Two", [1.0, 0.0]
        )
        assert store.count() == 2

        store.delete_by_chunk_ids(["chk-1"])
        assert store.count() == 1
        results = store.search(query_vector=[1.0, 0.0], top_k=5)
        assert len(results) == 1
        assert results[0].chunk_id == "chk-2"

    def test_empty_store_search_returns_empty(self, db_session) -> None:
        store = SqliteVectorStore(db_session)
        results = store.search(query_vector=[1.0, 0.0], top_k=5)
        assert results == []
