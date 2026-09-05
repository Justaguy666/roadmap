"""Unit tests for MarketIntelligenceService."""

from __future__ import annotations

from roadmap.domain.entities.source import Evidence, Source
from roadmap.domain.services.market_intelligence import MarketIntelligenceService
from roadmap.domain.value_objects import SourceType


def test_market_frequency_and_company_extraction() -> None:
    s1 = Source(
        id="s1",
        url="https://riotgames.com/careers/gameplay-engineer",
        title="Gameplay Engineer",
        source_type=SourceType.JOB_POSTING,
        domain="riotgames.com",
        publisher="Riot Games",
    )
    s2 = Source(
        id="s2",
        url="https://ubisoft.com/careers/vietnam/junior-programmer.vn",
        title="Junior Gameplay Programmer",
        source_type=SourceType.JOB_POSTING,
        domain="ubisoft.com.vn",
        publisher="Ubisoft Vietnam",
    )

    sources = {s1.id: s1, s2.id: s2}

    ev1 = Evidence(
        id="e1",
        source_id="s1",
        extracted_claim="Requires 3D math and vector operations.",
        relevance=0.90,
        confidence=0.95,
        associated_skill_names=["3D Math"],
    )
    ev2 = Evidence(
        id="e2",
        source_id="s2",
        extracted_claim="Linear algebra and 3D math required for physics interaction.",
        relevance=0.95,
        confidence=0.90,
        associated_skill_names=["3D Math"],
    )

    observations = MarketIntelligenceService.analyze_market_sample(
        target_role="Gameplay Programmer",
        evidence_items=[ev1, ev2],
        sources_by_id=sources,
        min_sample_threshold=2,
    )

    assert "3D Math" in observations
    obs = observations["3D Math"]
    assert obs.sample_size == 2
    assert obs.mentions == 2
    assert obs.observed_frequency == 1.0
    assert "Riot Games" in obs.unique_companies
    assert "Ubisoft Vietnam" in obs.unique_companies
    assert "Vietnam" in obs.market_regions
    assert obs.insufficient_sample is False


def test_insufficient_sample_flag() -> None:
    s = Source(
        id="s1",
        url="https://example.com/job",
        title="Developer",
        source_type=SourceType.JOB_POSTING,
    )
    ev = Evidence(
        id="e1",
        source_id="s1",
        extracted_claim="Requires C++.",
        associated_skill_names=["C++"],
    )

    obs = MarketIntelligenceService.analyze_market_sample(
        target_role="Developer",
        evidence_items=[ev],
        sources_by_id={s.id: s},
        min_sample_threshold=5,
    )

    assert obs["C++"].insufficient_sample is True
