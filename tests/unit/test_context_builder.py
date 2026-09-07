"""Unit tests for EvidenceContextBuilder and GroundedReasoningService validation."""

from __future__ import annotations

from unittest.mock import MagicMock

from roadmap.application.services.context_builder import EvidenceContextBuilder
from roadmap.application.services.grounded_reasoning_service import (
    GroundedAnswer,
    GroundedReasoningService,
)
from roadmap.domain.entities.knowledge import (
    EvidenceContext,
    EvidenceContextBlock,
    RetrievalResult,
)
from roadmap.domain.entities.source import Evidence, Source


class TestEvidenceContextBuilder:
    def test_build_context_from_results(self) -> None:
        mock_evidence_repo = MagicMock()
        mock_source_repo = MagicMock()

        evidence = Evidence(
            id="ev-123",
            source_id="src-456",
            extracted_claim="DirectX 12 requires explicit resource synchronization.",
            associated_skill_names=["DirectX 12", "Graphics"],
            confidence=0.9,
            relevance=0.85,
        )
        source = Source(
            id="src-456",
            url="https://microsoft.com/directx",
            title="DirectX 12 Programming Guide",
            domain="microsoft.com",
            reliability_score=0.95,
        )

        mock_evidence_repo.get_by_id.return_value = evidence
        mock_source_repo.get_by_id.return_value = source

        builder = EvidenceContextBuilder(
            evidence_repo=mock_evidence_repo,
            source_repo=mock_source_repo,
        )

        retrieval_results = [
            RetrievalResult(
                chunk_id="chk-1",
                document_id="doc-1",
                evidence_id="ev-123",
                similarity_score=0.92,
                rank=1,
                text="DirectX 12 requires explicit resource synchronization.",
                metadata={"title": "DirectX Guide"},
            )
        ]

        context = builder.build_context(
            query="DirectX synchronization",
            results=retrieval_results,
        )

        assert isinstance(context, EvidenceContext)
        assert context.query == "DirectX synchronization"
        assert len(context.blocks) == 1

        block = context.blocks[0]
        assert block.evidence_id == "ev-123"
        assert block.source_id == "src-456"
        assert block.source_title == "DirectX 12 Programming Guide"
        assert block.source_url == "https://microsoft.com/directx"
        assert block.is_authoritative is True
        assert "DirectX 12" in block.associated_skills

        prompt_str = context.format_prompt_context()
        assert "EVIDENCE ID: ev-123 [AUTHORITATIVE]" in prompt_str
        assert "Source: DirectX 12 Programming Guide" in prompt_str
        assert "DirectX 12 requires explicit resource synchronization." in prompt_str

    def test_missing_evidence_skipped(self) -> None:
        mock_evidence_repo = MagicMock()
        mock_source_repo = MagicMock()

        # Evidence not found in canonical database
        mock_evidence_repo.get_by_id.return_value = None

        builder = EvidenceContextBuilder(
            evidence_repo=mock_evidence_repo,
            source_repo=mock_source_repo,
        )

        results = [
            RetrievalResult(
                chunk_id="chk-orphan",
                document_id="doc-orphan",
                evidence_id="ev-ghost",
                similarity_score=0.99,
                rank=1,
                text="Phantom evidence",
                metadata={},
            )
        ]

        context = builder.build_context(query="test", results=results)
        # Authoritative truth check discards phantom evidence
        assert len(context.blocks) == 0


class TestGroundedReasoningService:
    def test_filter_ungrounded_citations_in_answer(self) -> None:
        mock_llm = MagicMock()

        # LLM proposes an answer citing 1 valid ID and 1 hallucinated ID
        mock_llm.complete.return_value = GroundedAnswer(
            answer="C++ requires explicit memory management.",
            cited_evidence_ids=["ev-valid-1", "ev-hallucinated-xyz"],
            confidence=0.95,
        )

        service = GroundedReasoningService(llm_provider=mock_llm)

        # Context has only ev-valid-1
        context = EvidenceContext(
            query="C++ memory",
            blocks=[
                EvidenceContextBlock(
                    evidence_id="ev-valid-1",
                    source_id="src-1",
                    source_title="C++ Docs",
                    source_url="",
                    is_authoritative=True,
                    excerpt="Pointers must be managed carefully.",
                    associated_skills=["C++"],
                ),
            ],
            total_retrieved_chunks=1,
            unique_evidence_count=1,
        )

        answer = service.answer_with_evidence(
            question="How does memory work in C++?",
            context=context,
        )

        # Hallucinated citation rejected deterministically
        assert answer.cited_evidence_ids == ["ev-valid-1"]
        assert answer.rejected_citations == ["ev-hallucinated-xyz"]
        assert answer.confidence < 0.95  # penalised for hallucinated citation
