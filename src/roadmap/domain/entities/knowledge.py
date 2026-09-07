"""Domain entities for Knowledge Intelligence: Documents, Chunks, Embeddings, and Retrieval.

Invariants:
- A KnowledgeDocument is derived from canonical Evidence (and optional parent Source).
- A KnowledgeChunk is a deterministic excerpt of a KnowledgeDocument.
- Vector similarity is solely a candidate retrieval mechanism, NOT authoritative truth.
- Every retrieved chunk remains strictly linked to its canonical evidence_id.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from roadmap.shared.ids import new_id


class DocumentStatus(str, Enum):
    """Indexing lifecycle status for a KnowledgeDocument."""

    PENDING = "PENDING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"


class KnowledgeDocument(BaseModel):
    """Represents an indexed document derived from canonical Evidence."""

    id: str = Field(default_factory=new_id)
    evidence_id: str = Field(description="Foreign ID of the canonical Evidence entity")
    source_id: str | None = Field(default=None, description="Foreign ID of the parent Source entity if known")
    title: str = Field(default="", max_length=500, description="Title of the source or document")
    content: str = Field(min_length=1, description="Full text extracted from canonical evidence")
    content_hash: str = Field(description="SHA-256 hash of content for idempotency and change detection")
    status: DocumentStatus = Field(default=DocumentStatus.PENDING)
    chunk_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata such as skill names, domain, etc.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_ready(self) -> bool:
        return self.status == DocumentStatus.READY


class KnowledgeChunk(BaseModel):
    """A deterministic, repeatable slice of a KnowledgeDocument."""

    id: str = Field(default_factory=new_id)
    document_id: str = Field(description="ID of the parent KnowledgeDocument")
    evidence_id: str = Field(description="Canonical evidence ID preserved from document")
    chunk_index: int = Field(ge=0, description="0-indexed sequence position in document")
    text: str = Field(min_length=1, description="Chunk textual content")
    content_hash: str = Field(description="SHA-256 hash of chunk text")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Copied/derived metadata from document")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EmbeddingRecord(BaseModel):
    """Persistent vector embedding linked to a specific KnowledgeChunk."""

    id: str = Field(default_factory=new_id)
    chunk_id: str = Field(description="ID of the KnowledgeChunk this vector represents")
    evidence_id: str = Field(description="Denormalized evidence ID for fast joins")
    provider: str = Field(description="Embedding provider name, e.g. 'gemini', 'openai', 'fake'")
    model: str = Field(description="Model identifier, e.g. 'text-embedding-004'")
    dimension: int = Field(gt=0, description="Vector length")
    embedding_version: str = Field(default="v1", description="Versioning string for embedding schema")
    vector: list[float] = Field(description="Normalized floating point vector values")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RetrievalFilter(BaseModel):
    """Deterministic filters applied to semantic search results."""

    provider: str | None = Field(default=None, description="Enforce matching embedding provider")
    model: str | None = Field(default=None, description="Enforce matching embedding model")
    skill_names: list[str] = Field(default_factory=list, description="Filter for chunks covering these skills")
    source_types: list[str] = Field(default_factory=list, description="Filter for specific source categories")
    domain: str | None = Field(default=None, description="Exact or suffix domain, e.g. 'github.com'")
    evidence_ids: list[str] = Field(default_factory=list, description="Explicit allowed evidence IDs")
    min_similarity: float | None = Field(default=None, ge=0.0, le=1.0, description="Override similarity cutoff")


class RetrievalQuery(BaseModel):
    """Semantic retrieval query parameters."""

    text: str = Field(min_length=1, description="Natural language search query")
    filter: RetrievalFilter = Field(default_factory=RetrievalFilter)
    top_k: int = Field(default=5, ge=1, le=50)


class RetrievalResult(BaseModel):
    """A scored semantic search hit linking directly to canonical evidence."""

    chunk_id: str
    document_id: str
    evidence_id: str
    similarity_score: float = Field(ge=-1.0, le=1.0)
    rank: int = Field(ge=1)
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceContextBlock(BaseModel):
    """A formatted block of evidence ready for LLM prompt ingestion."""

    evidence_id: str
    source_id: str | None = None
    source_url: str = ""
    source_title: str = ""
    publisher: str = ""
    is_authoritative: bool = False
    excerpt: str = ""
    confidence: float = 0.5
    relevance: float = 0.5
    associated_skills: list[str] = Field(default_factory=list)


class EvidenceContext(BaseModel):
    """Complete collection of grounded evidence prepared for RAG generation."""

    query: str
    blocks: list[EvidenceContextBlock] = Field(default_factory=list)
    total_retrieved_chunks: int = 0
    unique_evidence_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def cited_evidence_ids(self) -> set[str]:
        return {b.evidence_id for b in self.blocks}

    def format_prompt_context(self) -> str:
        """Render deterministic prompt-ready text with strict evidence delimiters."""
        if not self.blocks:
            return "No relevant research evidence found."

        lines: list[str] = ["=== RETRIEVED RESEARCH EVIDENCE (CANONICAL SOURCES ONLY) ==="]
        for idx, block in enumerate(self.blocks, start=1):
            auth_tag = " [AUTHORITATIVE]" if block.is_authoritative else ""
            lines.append(f"[{idx}] EVIDENCE ID: {block.evidence_id}{auth_tag}")
            if block.source_title:
                lines.append(f"    Source: {block.source_title}")
            if block.source_url:
                lines.append(f"    URL: {block.source_url}")
            if block.associated_skills:
                lines.append(f"    Skills: {', '.join(block.associated_skills)}")
            lines.append("    Claim Excerpt:")
            for line in block.excerpt.strip().splitlines():
                lines.append(f"      {line}")
            lines.append("")
        lines.append("=== END OF RETRIEVED EVIDENCE ===")
        return "\n".join(lines)

