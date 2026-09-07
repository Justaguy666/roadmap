"""Application service: RAGService.

High-level RAG orchestration layer cleanly separating Retrieval from Generation:
- Validates search parameters.
- Invokes SemanticRetrievalService.
- Passes retrieved hits to EvidenceContextBuilder.
- Returns structured EvidenceContext without forced LLM calls.
"""

from __future__ import annotations

from roadmap.application.services.context_builder import EvidenceContextBuilder
from roadmap.application.services.semantic_retrieval_service import SemanticRetrievalService
from roadmap.domain.entities.knowledge import (
    EvidenceContext,
    RetrievalFilter,
    RetrievalQuery,
)


class RAGService:
    """Orchestrates end-to-end evidence retrieval and context building."""

    def __init__(
        self,
        retrieval_service: SemanticRetrievalService,
        context_builder: EvidenceContextBuilder,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.context_builder = context_builder

    def retrieve_context(
        self,
        query: str | RetrievalQuery,
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
        max_context_length: int = 4000,
    ) -> EvidenceContext:
        """
        Execute RAG retrieval pipeline and produce verified EvidenceContext.
        Does NOT invoke an LLM.
        """
        results = self.retrieval_service.retrieve(
            query=query,
            top_k=top_k,
            filters=filters,
        )

        query_str = query if isinstance(query, str) else query.text
        return self.context_builder.build_context(
            query=query_str,
            results=results,
            max_context_length=max_context_length,
        )
