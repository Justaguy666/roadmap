"""API schemas for Knowledge / RAG search endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    """Query parameters for GET /api/v1/profiles/{id}/knowledge/search."""

    query: str = Field(min_length=1, max_length=1000, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of results to return")
    threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold (0.0 – 1.0)",
    )
    skill_name: str | None = Field(default=None, description="Filter results by skill name")
    domain: str | None = Field(default=None, description="Filter results by source domain")


class KnowledgeSearchResultItem(BaseModel):
    """A single evidence-grounded search result."""

    evidence_id: str
    source_title: str
    source_url: str
    is_authoritative: bool
    excerpt: str
    associated_skills: list[str]


class KnowledgeSearchResponse(BaseModel):
    """Response body for knowledge search endpoints."""

    query: str
    retrieved_count: int
    results: list[KnowledgeSearchResultItem]
