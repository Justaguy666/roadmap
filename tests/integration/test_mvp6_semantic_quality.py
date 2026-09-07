"""Integration tests for MVP-6: Identity tuple, re-indexing, partial failure, budget separation, and semantic quality."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from roadmap.application.ports.embedding_provider import EmbeddingProviderError
from roadmap.application.services.knowledge_indexing_service import KnowledgeIndexingService
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.application.services.semantic_retrieval_service import SemanticRetrievalService
from roadmap.config.settings import settings
from roadmap.domain.entities.knowledge import DocumentStatus
from roadmap.domain.services.knowledge_chunker import KnowledgeChunker
from roadmap.domain.value_objects.enums import LLMWorkflow
from roadmap.infrastructure.embeddings.fake_embedding_provider import FakeEmbeddingProvider
from roadmap.infrastructure.embeddings.gemini_embedding_provider import GeminiEmbeddingProvider
from roadmap.infrastructure.vector_store.sqlite_vector_store import SqliteVectorStore
from roadmap.storage.models.knowledge_model import KnowledgeDocumentModel
from roadmap.storage.models.progress_model import SourceModel
from roadmap.storage.models.research_model import EvidenceModel
from roadmap.storage.repositories.knowledge_repository import SqliteKnowledgeRepository
from roadmap.storage.repositories.llm_usage_repository import SqliteLLMUsageRepository
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteSourceRepository,
)


def _seed_test_evidence(session, ev_id: str = "ev-1", claim: str = "C++ pointers and memory management.") -> EvidenceModel:
    now = datetime.now(UTC)
    src = session.query(SourceModel).filter_by(id="src-test").first()
    if not src:
        src = SourceModel(
            id="src-test",
            url="https://example.com/test",
            title="Test Source",
            source_type="documentation",
            reliability_score=0.9,
            retrieved_at=now,
        )
        session.add(src)
        session.flush()

    ev = EvidenceModel(
        id=ev_id,
        source_id=src.id,
        extracted_claim=claim,
        relevance=0.9,
        confidence=0.9,
        associated_skill_names_json=json.dumps(["C++"]),
        created_at=now,
    )
    session.add(ev)
    session.flush()
    return ev


class TestEmbeddingIdentityAndReindexing:
    def test_identity_tuple_controls_reuse(self, db_session) -> None:
        _seed_test_evidence(db_session, "ev-ident", "C++ memory management and smart pointers.")

        evidence_repo = SqliteEvidenceRepository(db_session)
        source_repo = SqliteSourceRepository(db_session)
        knowledge_repo = SqliteKnowledgeRepository(db_session)
        chunker = KnowledgeChunker()

        prov_v1 = FakeEmbeddingProvider(dimension=768, model_name="model-alpha")
        indexer_v1 = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=prov_v1,
            chunker=chunker,
        )

        # 1. Initial index with model-alpha
        s1 = indexer_v1.index_all_evidence()
        assert s1["documents"] == 1

        # 2. Same content + same model -> reuse allowed (0 documents re-indexed)
        s2 = indexer_v1.index_all_evidence()
        assert s2["documents"] == 0

        # 3. Same content + DIFFERENT model -> reuse forbidden (re-indexed with new model)
        prov_v2 = FakeEmbeddingProvider(dimension=768, model_name="model-beta")
        indexer_v2 = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=prov_v2,
            chunker=chunker,
        )
        s3 = indexer_v2.index_all_evidence()
        assert s3["documents"] == 1
        doc = db_session.query(KnowledgeDocumentModel).filter_by(evidence_id="ev-ident").one()
        assert doc.metadata_dict.get("embedding_model") == "model-beta"

        # 4. Same content + DIFFERENT dimension -> reuse forbidden (re-indexed with new dim)
        prov_v3 = FakeEmbeddingProvider(dimension=384, model_name="model-beta")
        indexer_v3 = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=prov_v3,
            chunker=chunker,
        )
        s4 = indexer_v3.index_all_evidence()
        assert s4["documents"] == 1
        doc = db_session.query(KnowledgeDocumentModel).filter_by(evidence_id="ev-ident").one()
        assert doc.metadata_dict.get("embedding_dimension") == 384


class TestPartialIndexFailure:
    def test_failure_marks_document_failed_and_recovers(self, db_session) -> None:
        _seed_test_evidence(db_session, "ev-fail", "Claim for partial failure testing.")

        evidence_repo = SqliteEvidenceRepository(db_session)
        source_repo = SqliteSourceRepository(db_session)
        knowledge_repo = SqliteKnowledgeRepository(db_session)

        # Provider that raises an error during embed_batch
        failing_provider = MagicMock()
        failing_provider.provider_name = "fake"
        failing_provider.model_name = "failing-model"
        failing_provider.dimension = 768
        failing_provider.embed_batch.side_effect = EmbeddingProviderError("Simulated embedding outage")

        failing_indexer = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=failing_provider,
        )

        with pytest.raises(EmbeddingProviderError):
            failing_indexer.index_all_evidence()

        doc = db_session.query(KnowledgeDocumentModel).filter_by(evidence_id="ev-fail").one()
        # Invariant: Document MUST NOT become READY on partial/failed embedding
        assert doc.status == DocumentStatus.FAILED

        # Recovery: Subsequent run with working provider succeeds
        working_provider = FakeEmbeddingProvider(dimension=768, model_name="working-model")
        working_indexer = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=working_provider,
        )

        summary = working_indexer.index_all_evidence()
        assert summary["documents"] == 1
        updated_doc = db_session.query(KnowledgeDocumentModel).filter_by(evidence_id="ev-fail").one()
        assert updated_doc.status == DocumentStatus.READY


class TestLLMBudgetSeparation:
    def test_embedding_and_retrieval_do_not_consume_llm_budget(self, db_session) -> None:
        _seed_test_evidence(db_session, "ev-budget", "Evidence for budget independence.")

        usage_repo = SqliteLLMUsageRepository(db_session)
        budget_manager = LLMBudgetManager(repository=usage_repo)
        status_before = budget_manager.get_quota_status()
        gen_before = status_before.workflow_budgets[LLMWorkflow.GENERATION].used
        adapt_before = status_before.workflow_budgets[LLMWorkflow.ADAPTATION].used

        # Run indexing
        evidence_repo = SqliteEvidenceRepository(db_session)
        source_repo = SqliteSourceRepository(db_session)
        knowledge_repo = SqliteKnowledgeRepository(db_session)
        vector_store = SqliteVectorStore(db_session)
        provider = FakeEmbeddingProvider(dimension=768)

        indexer = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=provider,
        )
        indexer.index_all_evidence()

        # Run retrieval
        retriever = SemanticRetrievalService(
            embedding_provider=provider,
            vector_store=vector_store,
            evidence_repo=evidence_repo,
            source_repo=source_repo,
        )
        retriever.retrieve("C++ pointers")

        status_after = budget_manager.get_quota_status()
        gen_after = status_after.workflow_budgets[LLMWorkflow.GENERATION].used
        adapt_after = status_after.workflow_budgets[LLMWorkflow.ADAPTATION].used

        # Invariant: Embedding and search operations must NOT increment LLM generation/adaptation budget
        assert gen_before == gen_after == 0
        assert adapt_before == adapt_after == 0


class TestSemanticQualityRegressionFixture:
    """
    Semantic Quality Tests.
    Explicitly separated from Infrastructure Tests.
    Tests semantic retrieval accuracy across 5 distinct domains.
    """

    @pytest.mark.skipif(
        not settings.gemini_api_key,
        reason="Real Gemini API key required for empirical semantic retrieval quality test",
    )
    def test_empirical_semantic_retrieval_ranking(self, db_session) -> None:
        now = datetime.now(UTC)
        src = SourceModel(
            id="src-quality",
            url="https://quality.example.com",
            title="Quality Benchmark Source",
            source_type="curriculum",
            reliability_score=0.95,
            retrieved_at=now,
        )
        db_session.add(src)
        db_session.flush()

        corpus_data = [
            ("ev-q-cpp", "Deep understanding of C++ memory models, pointers, RAII, and manual heap allocation."),
            ("ev-q-ai", "Behavior trees, navigation meshes, pathfinding, and decision-making for NPCs."),
            ("ev-q-test", "Unit testing, integration tests, test-driven development, and CI/CD pipelines."),
            ("ev-q-render", "Vulkan, DirectX 12 shaders, rasterization, and GPU graphics rendering pipelines."),
            ("ev-q-git", "Git branching strategies, rebasing, pull requests, and resolving merge conflicts."),
        ]

        for ev_id, text in corpus_data:
            db_session.add(
                EvidenceModel(
                    id=ev_id,
                    source_id=src.id,
                    extracted_claim=text,
                    relevance=0.9,
                    confidence=0.9,
                    created_at=now,
                )
            )
        db_session.flush()

        evidence_repo = SqliteEvidenceRepository(db_session)
        source_repo = SqliteSourceRepository(db_session)
        knowledge_repo = SqliteKnowledgeRepository(db_session)
        vector_store = SqliteVectorStore(db_session)
        provider = GeminiEmbeddingProvider(model="gemini-embedding-001", dimension=768)

        indexer = KnowledgeIndexingService(
            evidence_repo=evidence_repo,
            source_repo=source_repo,
            knowledge_repo=knowledge_repo,
            embedding_provider=provider,
        )
        indexer.index_all_evidence(force=True)

        retriever = SemanticRetrievalService(
            embedding_provider=provider,
            vector_store=vector_store,
            evidence_repo=evidence_repo,
            source_repo=source_repo,
        )

        test_cases = [
            ("memory management in C++", "ev-q-cpp"),
            ("gameplay AI", "ev-q-ai"),
            ("automated software testing", "ev-q-test"),
            ("rendering pipeline", "ev-q-render"),
        ]

        for query_text, expected_ev_id in test_cases:
            results = retriever.retrieve(query=query_text, top_k=3)
            assert len(results) > 0, f"Expected results for '{query_text}'"
            top_hit = results[0]
            assert top_hit.evidence_id == expected_ev_id, (
                f"Query '{query_text}' expected top hit '{expected_ev_id}', got '{top_hit.evidence_id}'"
            )
