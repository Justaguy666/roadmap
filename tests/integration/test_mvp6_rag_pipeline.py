"""Integration tests for MVP-6 Semantic Retrieval and Grounded RAG Pipeline."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

from roadmap.application.services.context_builder import EvidenceContextBuilder
from roadmap.application.services.grounded_reasoning_service import (
    GroundedAnswer,
    GroundedReasoningService,
)
from roadmap.application.services.knowledge_indexing_service import KnowledgeIndexingService
from roadmap.application.services.rag_service import RAGService
from roadmap.application.services.semantic_retrieval_service import SemanticRetrievalService
from roadmap.domain.entities.knowledge import RetrievalFilter
from roadmap.domain.services.knowledge_chunker import KnowledgeChunker
from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from roadmap.infrastructure.vector_store.sqlite_vector_store import SqliteVectorStore
from roadmap.storage.models.progress_model import SourceModel
from roadmap.storage.models.research_model import EvidenceModel
from roadmap.storage.repositories.knowledge_repository import SqliteKnowledgeRepository
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteSourceRepository,
)


def _seed_rag_test_data(session) -> tuple[str, str]:
    now = datetime.now(UTC)
    src_larian = SourceModel(
        id="src-larian",
        url="https://jobs.lever.co/larian/gameplay",
        title="Larian Studios - Gameplay Programmer",
        source_type="job_posting",
        publisher="Larian",
        domain="larian.com",
        reliability_score=0.95,
        retrieved_at=now,
    )
    src_blog = SourceModel(
        id="src-blog",
        url="https://floooh.github.io/ecs-blog",
        title="Data-Oriented Tech Blog",
        source_type="article",
        publisher="Andre",
        domain="floooh.github.io",
        reliability_score=0.75,
        retrieved_at=now,
    )
    session.add_all([src_larian, src_blog])
    session.flush()

    ev1 = EvidenceModel(
        id="ev-larian-cpp",
        source_id="src-larian",
        extracted_claim="Requires strong knowledge of C++ pointer arithmetic, memory management, and RAII.",
        relevance=0.9,
        confidence=0.9,
        associated_skill_names_json=json.dumps(["C++", "Memory Management"]),
        created_at=now,
    )
    ev2 = EvidenceModel(
        id="ev-ecs-cache",
        source_id="src-blog",
        extracted_claim="Entity Component Systems optimize memory layout for CPU L1/L2 cache coherency.",
        relevance=0.85,
        confidence=0.8,
        associated_skill_names_json=json.dumps(["ECS", "Data-Oriented Design"]),
        created_at=now,
    )
    session.add_all([ev1, ev2])
    session.flush()
    return ev1.id, ev2.id


class TestMVP6RAGPipeline:
    def test_end_to_end_retrieval_and_grounding(self, db_session) -> None:
        ev1_id, ev2_id = _seed_rag_test_data(db_session)

        # Repositories & Services
        evidence_repo = SqliteEvidenceRepository(db_session)
        source_repo = SqliteSourceRepository(db_session)
        knowledge_repo = SqliteKnowledgeRepository(db_session)
        vector_store = SqliteVectorStore(db_session)
        embedding_provider = FakeEmbeddingProvider(dimension=768)
        chunker = KnowledgeChunker(chunk_size=200, chunk_overlap=20)

        # 1. Index evidence into knowledge tables
        indexer = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=embedding_provider,
            chunker=chunker,
        )
        summary = indexer.index_all_evidence()
        assert summary["documents"] == 2

        # 2. Setup RAG components
        retrieval_service = SemanticRetrievalService(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            evidence_repo=evidence_repo,
            source_repo=source_repo,
        )
        context_builder = EvidenceContextBuilder(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
        )
        rag_service = RAGService(
            retrieval_service=retrieval_service,
            context_builder=context_builder,
        )

        # 3. Retrieve context
        context = rag_service.retrieve_context(
            query="C++ pointer arithmetic and memory",
            top_k=5,
        )
        assert len(context.blocks) >= 1
        assert ev1_id in context.cited_evidence_ids

        # Check block fields
        cpp_block = next(b for b in context.blocks if b.evidence_id == ev1_id)
        assert cpp_block.source_title == "Larian Studios - Gameplay Programmer"
        assert cpp_block.source_url == "https://jobs.lever.co/larian/gameplay"
        assert cpp_block.is_authoritative is True
        assert "C++" in cpp_block.associated_skills

        # 4. Metadata filter by skill
        ecs_context = rag_service.retrieve_context(
            query="memory layout optimization",
            top_k=5,
            filters=RetrievalFilter(skill_names=["ECS"]),
        )
        assert len(ecs_context.blocks) == 1
        assert ecs_context.blocks[0].evidence_id == ev2_id

        # 5. Grounded reasoning with fake LLM
        mock_llm = MagicMock()
        mock_llm.complete.return_value = GroundedAnswer(
            answer="In game engines, C++ pointer arithmetic and RAII are required by Larian Studios.",
            cited_evidence_ids=[ev1_id, "ev-invented-by-llm"],
            confidence=0.9,
        )

        reasoning_service = GroundedReasoningService(llm_provider=mock_llm)
        final_answer = reasoning_service.answer_with_evidence(
            question="What memory management skills are required?",
            context=context,
        )

        # Verification of deterministic anti-hallucination citation gate
        assert ev1_id in final_answer.cited_evidence_ids
        assert "ev-invented-by-llm" not in final_answer.cited_evidence_ids
        assert "ev-invented-by-llm" in final_answer.rejected_citations
