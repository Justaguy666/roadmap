"""Unit tests for EvidenceAggregator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from roadmap.domain.entities.source import Evidence, Source
from roadmap.domain.services.evidence_aggregator import EvidenceAggregator
from roadmap.domain.value_objects import SourceType


def test_evidence_weighting_and_bonus() -> None:
    now = datetime.now(UTC)
    s1 = Source(
        id="s1",
        url="https://epicgames.com/careers/engine-programmer",
        title="Engine Programmer",
        source_type=SourceType.JOB_POSTING,
        domain="epicgames.com",
        reliability_score=0.90,
        published_at=now - timedelta(days=30),
    )
    s2 = Source(
        id="s2",
        url="https://learn.microsoft.com/en-us/cpp",
        title="C++ Documentation",
        source_type=SourceType.OFFICIAL_DOCS,
        domain="microsoft.com",
        reliability_score=0.95,
        published_at=now - timedelta(days=60),
    )

    sources = {s1.id: s1, s2.id: s2}

    ev1 = Evidence(
        id="e1",
        source_id="s1",
        extracted_claim="Requires deep mastery of modern C++ (C++17/20) and memory management.",
        relevance=0.95,
        confidence=0.90,
        associated_skill_names=["C++"],
    )
    ev2 = Evidence(
        id="e2",
        source_id="s2",
        extracted_claim="C++ reference guide for RAII and move semantics.",
        relevance=0.85,
        confidence=0.95,
        associated_skill_names=["C++"],
    )

    summary = EvidenceAggregator.aggregate_for_skill("C++", [ev1, ev2], sources)
    assert summary.skill_name == "C++"
    assert summary.evidence_count == 2
    assert summary.unique_source_count == 2
    assert summary.weighted_score > 0.70
    assert "epicgames.com" in summary.supporting_domains
    assert "microsoft.com" in summary.supporting_domains
    assert len(summary.divergence_notes) == 0


def test_divergence_and_caveat_detection() -> None:
    s = Source(
        id="s1",
        url="https://example.com/legacy-cpp",
        title="Legacy C++ Notes",
        source_type=SourceType.BLOG_POST,
        reliability_score=0.70,
    )
    ev = Evidence(
        id="e1",
        source_id="s1",
        extracted_claim="Raw pointers and manual delete are obsolete and not recommended in modern standards.",
        relevance=0.90,
        confidence=0.90,
        associated_skill_names=["Raw Pointers"],
    )

    summary = EvidenceAggregator.aggregate_for_skill("Raw Pointers", [ev], {s.id: s})
    assert len(summary.contradicting_evidence_ids) == 1
    assert any("Caveat/Contradiction noted" in n for n in summary.divergence_notes)
