"""Application service: EvidenceContextBuilder.

Builds structured, citation-ready EvidenceContext for LLM prompt ingestion:
- Resolves RetrievalResults to canonical Evidence and Source records.
- Deduplicates claims referring to the same evidence ID.
- Formats context blocks with explicit IDs, source URLs, and authoritativeness flags.
- Rejects ungrounded or synthetic evidence references.
"""

from __future__ import annotations

from datetime import UTC, datetime

from roadmap.domain.entities.knowledge import (
    EvidenceContext,
    EvidenceContextBlock,
    RetrievalResult,
)
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteSourceRepository,
)


class EvidenceContextBuilder:
    """Builds LLM-ready prompt context from semantic retrieval results."""

    def __init__(
        self,
        evidence_repo: SqliteEvidenceRepository,
        source_repo: SqliteSourceRepository,
    ) -> None:
        self.evidence_repo = evidence_repo
        self.source_repo = source_repo

    def build_context(
        self,
        query: str,
        results: list[RetrievalResult],
        max_context_length: int = 4000,
    ) -> EvidenceContext:
        """
        Convert ranked RetrievalResults into a structured EvidenceContext.
        Deduplicates identical evidence IDs while preserving highest ranked excerpt.
        """
        seen_evidence_ids: set[str] = set()
        blocks: list[EvidenceContextBlock] = []
        accumulated_chars = 0

        for r in results:
            if r.evidence_id in seen_evidence_ids:
                continue

            ev = self.evidence_repo.get_by_id(r.evidence_id)
            if not ev:
                continue

            source = self.source_repo.get_by_id(ev.source_id)

            block = EvidenceContextBlock(
                evidence_id=ev.id,
                source_id=ev.source_id,
                source_url=source.url if source else "",
                source_title=source.title if source else "",
                publisher=source.publisher if source else "",
                is_authoritative=source.is_authoritative if source else False,
                excerpt=r.text,
                confidence=ev.confidence,
                relevance=ev.relevance,
                associated_skills=ev.associated_skill_names,
            )

            block_len = len(block.excerpt) + len(block.source_title) + 100
            if accumulated_chars + block_len > max_context_length and blocks:
                break

            blocks.append(block)
            seen_evidence_ids.add(ev.id)
            accumulated_chars += block_len

        return EvidenceContext(
            query=query,
            blocks=blocks,
            total_retrieved_chunks=len(results),
            unique_evidence_count=len(blocks),
            created_at=datetime.now(UTC),
        )
