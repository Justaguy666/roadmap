"""Unit tests for deterministic KnowledgeChunker."""

from __future__ import annotations

import hashlib

from roadmap.domain.entities.knowledge import KnowledgeDocument
from roadmap.domain.services.knowledge_chunker import KnowledgeChunker


def _make_doc(text: str, doc_id: str = "doc-1", ev_id: str = "ev-1", metadata: dict | None = None) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=doc_id,
        evidence_id=ev_id,
        content=text,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        metadata=metadata or {},
    )


class TestKnowledgeChunker:
    def test_empty_content_returns_empty_list(self) -> None:
        chunker = KnowledgeChunker(chunk_size=100, chunk_overlap=20)
        assert chunker.split_text("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        chunker = KnowledgeChunker(chunk_size=100, chunk_overlap=20)
        assert chunker.split_text("   \n\n\t  ") == []

    def test_short_content_returns_single_chunk(self) -> None:
        chunker = KnowledgeChunker(chunk_size=100, chunk_overlap=20)
        text = "C++ memory management requires understanding pointers and RAII."
        chunks = chunker.chunk_document(_make_doc(text))
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].text == text
        assert chunks[0].document_id == "doc-1"
        assert chunks[0].evidence_id == "ev-1"
        assert len(chunks[0].content_hash) == 64

    def test_deterministic_hashing(self) -> None:
        chunker = KnowledgeChunker(chunk_size=100, chunk_overlap=20)
        text = "Identical text should produce identical content hashes."
        chunks_a = chunker.chunk_document(_make_doc(text, doc_id="doc-1", ev_id="ev-1"))
        chunks_b = chunker.chunk_document(_make_doc(text, doc_id="doc-2", ev_id="ev-2"))
        assert chunks_a[0].content_hash == chunks_b[0].content_hash

    def test_long_content_splits_with_natural_breaks(self) -> None:
        chunker = KnowledgeChunker(chunk_size=60, chunk_overlap=15)
        text = (
            "First sentence about compilers.\n"
            "Second sentence about memory management.\n"
            "Third sentence about data-oriented design."
        )
        chunks = chunker.chunk_document(_make_doc(text))
        assert len(chunks) >= 2
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert len(chunk.text) <= 80

    def test_chunk_overlap_preserves_context(self) -> None:
        chunker = KnowledgeChunker(chunk_size=50, chunk_overlap=20)
        text = "0123456789" * 15  # 150 chars without natural breaks
        chunks = chunker.chunk_document(_make_doc(text))
        assert len(chunks) > 1
        # Consecutive chunks should share overlapping characters
        tail_of_first = chunks[0].text[-10:]
        assert tail_of_first in chunks[1].text

    def test_max_chunks_limit_enforced(self) -> None:
        chunker = KnowledgeChunker(chunk_size=20, chunk_overlap=5, max_chunks_per_doc=3)
        text = "word " * 100
        chunks = chunker.chunk_document(_make_doc(text))
        assert len(chunks) <= 3

    def test_unicode_and_symbols_supported(self) -> None:
        chunker = KnowledgeChunker(chunk_size=80, chunk_overlap=10)
        text = "Nhúng mã độc và tối ưu bộ nhớ 🚀 with C++20 coroutines và SIMD instructions."
        chunks = chunker.chunk_document(_make_doc(text))
        assert len(chunks) >= 1
        assert "🚀" in chunks[0].text

    def test_metadata_propagated(self) -> None:
        chunker = KnowledgeChunker(chunk_size=100, chunk_overlap=20)
        metadata = {"skill": "C++", "domain": "gamedev.net"}
        doc = _make_doc(
            "Understanding smart pointers in modern C++.",
            metadata=metadata,
        )
        chunks = chunker.chunk_document(doc)
        assert chunks[0].metadata["skill"] == "C++"
        assert chunks[0].metadata["domain"] == "gamedev.net"
        assert chunks[0].metadata["chunk_index"] == 0

    def test_split_text_pure(self) -> None:
        chunker = KnowledgeChunker(chunk_size=50, chunk_overlap=10)
        slices = chunker.split_text("Alpha beta gamma delta epsilon zeta eta theta iota kappa.")
        assert len(slices) >= 1
        assert isinstance(slices[0], str)
