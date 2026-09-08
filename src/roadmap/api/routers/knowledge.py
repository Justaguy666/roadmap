"""Knowledge search endpoint: GET /api/v1/profiles/{profile_id}/knowledge/search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from roadmap.api.dependencies import get_authorized_profile, get_rag_service
from roadmap.api.schemas.common import ErrorCode
from roadmap.api.schemas.knowledge import KnowledgeSearchResponse, KnowledgeSearchResultItem
from roadmap.application.ports.embedding_provider import EmbeddingProviderError
from roadmap.application.ports.llm_provider import MissingAPIKeyError
from roadmap.application.services.rag_service import RAGService
from roadmap.config.settings import settings
from roadmap.domain.entities.knowledge import RetrievalFilter
from roadmap.domain.entities.user_profile import UserProfile

router = APIRouter(tags=["Knowledge"])


@router.get(
    "/profiles/{profile_id}/knowledge/search",
    response_model=KnowledgeSearchResponse,
    summary="Semantic knowledge search",
    description=(
        "Executes semantic vector similarity retrieval against the indexed knowledge base. "
        "Does NOT call the LLM. "
        "All results preserve canonical evidence_id, source_id, and source_url provenance. "
        "Vector similarity is a retrieval mechanism only, not authoritative truth."
    ),
    responses={
        400: {"description": "Invalid query parameters"},
        401: {"description": "Authentication required"},
        404: {"description": "Profile not found"},
    },
)
def knowledge_search(
    query: str = Query(min_length=1, max_length=1000, description="Natural language search query"),
    top_k: int = Query(default=5, ge=1, le=50, description="Maximum number of results"),
    threshold: float | None = Query(default=None, ge=0.0, le=1.0, description="Minimum similarity threshold"),
    skill_name: str | None = Query(default=None, description="Filter by skill name"),
    domain: str | None = Query(default=None, description="Filter by source domain"),
    profile: UserProfile = Depends(get_authorized_profile),
    rag_service: RAGService = Depends(get_rag_service),
) -> KnowledgeSearchResponse:
    """
    Execute semantic knowledge search.

    Calls SemanticRetrievalService -> EvidenceContextBuilder.
    Does NOT bypass the RAG/retrieval service.
    Does NOT query vector tables directly.
    Preserves canonical evidence_id/source_id/source_url.
    """
    effective_threshold = threshold if threshold is not None else settings.rag_similarity_threshold
    filters = RetrievalFilter(
        skill_names=[skill_name] if skill_name else [],
        domain=domain,
        min_similarity=effective_threshold,
    )

    try:
        context = rag_service.retrieve_context(
            query=query,
            top_k=top_k,
            filters=filters,
        )
    except (EmbeddingProviderError, MissingAPIKeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": ErrorCode.PROVIDER_ERROR, "message": "Embedding provider is unavailable"}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": ErrorCode.PROVIDER_ERROR, "message": str(exc)}},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": ErrorCode.INTERNAL_ERROR, "message": "Knowledge search failed"}},
        ) from exc


    results = [
        KnowledgeSearchResultItem(
            evidence_id=block.evidence_id,
            source_title=block.source_title or "",
            source_url=block.source_url or "",
            is_authoritative=block.is_authoritative,
            excerpt=block.excerpt,
            associated_skills=block.associated_skills,
        )
        for block in context.blocks
    ]

    return KnowledgeSearchResponse(
        query=context.query,
        retrieved_count=len(results),
        results=results,
    )
