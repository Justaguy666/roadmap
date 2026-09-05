"""Tests for SourceScorer and URL normalizer."""

from datetime import UTC, datetime, timedelta

from roadmap.domain.entities.source import Source
from roadmap.domain.services.source_scorer import SourceScorer
from roadmap.domain.services.url_normalizer import normalize_url
from roadmap.domain.value_objects import SourceType


def test_url_normalizer_removes_tracking_and_anchors() -> None:
    raw = "https://example.com/learn/python/?utm_source=twitter&utm_medium=cpc#introduction"
    normalized = normalize_url(raw)
    assert normalized == "https://example.com/learn/python"


def test_url_normalizer_sorts_query_parameters() -> None:
    raw = "https://api.github.com/repos?b=2&a=1"
    normalized = normalize_url(raw)
    assert normalized == "https://api.github.com/repos?a=1&b=2"


def test_url_normalizer_strips_default_ports_and_trailing_slash() -> None:
    raw = "https://docs.python.org:443/3/library/"
    normalized = normalize_url(raw)
    assert normalized == "https://docs.python.org/3/library"


def test_source_scorer_official_docs_and_bonus() -> None:
    source = Source(
        url="https://docs.python.org/3/",
        domain="docs.python.org",
        source_type=SourceType.OFFICIAL_DOCS,
        published_at=datetime.now(UTC),
    )
    score = SourceScorer.score(source)
    # Base 0.95 + 0.05 bonus - 0 decay = 1.0 (clamped)
    assert score >= 0.95
    assert score <= 1.0


def test_source_scorer_penalizes_old_content() -> None:
    fresh_source = Source(
        url="https://medium.com/article1",
        domain="medium.com",
        source_type=SourceType.ARTICLE,
        published_at=datetime.now(UTC),
    )
    old_source = Source(
        url="https://medium.com/article2",
        domain="medium.com",
        source_type=SourceType.ARTICLE,
        published_at=datetime.now(UTC) - timedelta(days=365 * 4),
    )

    fresh_score = SourceScorer.score(fresh_source)
    old_score = SourceScorer.score(old_source)

    assert fresh_score > old_score
    assert old_score < 0.60
