"""Domain service: KnowledgeChunker.

Provides pure deterministic, repeatable text chunking with token/character boundary
awareness, configurable chunk size and overlap, document order preservation,
and zero external or LLM dependencies.
"""

from __future__ import annotations

import hashlib
import re

from roadmap.domain.entities.knowledge import KnowledgeChunk, KnowledgeDocument
from roadmap.shared.ids import new_id


class KnowledgeChunker:
    """Deterministic text chunking engine."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        max_chunks_per_doc: int = 50,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap cannot be negative, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be strictly less than chunk_size ({chunk_size})"
            )
        if max_chunks_per_doc <= 0:
            raise ValueError(f"max_chunks_per_doc must be positive, got {max_chunks_per_doc}")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunks_per_doc = max_chunks_per_doc

    def chunk_document(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        """Decompose a KnowledgeDocument into ordered KnowledgeChunks deterministically."""
        text = document.content.strip()
        if not text:
            return []

        text_chunks = self.split_text(text)
        chunks: list[KnowledgeChunk] = []

        for idx, chunk_text in enumerate(text_chunks[: self.max_chunks_per_doc]):
            content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            chunk_metadata = {
                **document.metadata,
                "chunk_index": idx,
                "char_length": len(chunk_text),
            }
            chunks.append(
                KnowledgeChunk(
                    id=new_id(),
                    document_id=document.id,
                    evidence_id=document.evidence_id,
                    chunk_index=idx,
                    text=chunk_text,
                    content_hash=content_hash,
                    metadata=chunk_metadata,
                )
            )

        return chunks

    def split_text(self, text: str) -> list[str]:
        """
        Deterministic sliding window text splitting.
        Attempts to break chunks on paragraph or sentence boundaries when feasible,
        falling back to character slices to strictly honor chunk_size bounds.
        """
        cleaned = re.sub(r"\r\n", "\n", text.strip())
        if not cleaned:
            return []

        if len(cleaned) <= self.chunk_size:
            return [cleaned]

        chunks: list[str] = []
        start = 0
        text_len = len(cleaned)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            candidate = cleaned[start:end]

            if end < text_len:
                # Look for natural breaking points near the end
                split_point = -1
                for sep in ("\n\n", "\n", ". ", "? ", "! ", "; ", " "):
                    pos = candidate.rfind(sep)
                    if pos > self.chunk_size // 2:
                        split_point = pos + len(sep)
                        break

                if split_point != -1:
                    chunk_text = candidate[:split_point].strip()
                    advance = split_point
                else:
                    chunk_text = candidate.strip()
                    advance = self.chunk_size
            else:
                chunk_text = candidate.strip()
                advance = len(candidate)

            if chunk_text:
                chunks.append(chunk_text)

            # Advance by (advance - overlap)
            step = max(1, advance - self.chunk_overlap)
            start += step

            if len(chunks) >= self.max_chunks_per_doc:
                break

        return chunks
