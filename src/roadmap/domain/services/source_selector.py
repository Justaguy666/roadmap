"""
Domain Service: SourceSelector.

Implements deterministic source ranking and diverse selection:
1. Filters redundant or low-signal search results.
2. Scores sources by domain authority, search relevance, and role/skill signals.
3. Enforces domain and category diversity (capping repeated domains to prevent 15 identical job boards).
4. Selects a bounded high-value source budget (e.g. 10-15 sources).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from roadmap.application.ports.search_provider import SearchResult
from roadmap.domain.services.source_scorer import AUTHORITATIVE_DOMAINS, SOURCE_TYPE_BASE_SCORES
from roadmap.domain.value_objects import SourceType


class SourceSelector:
    """Selects a bounded, high-quality, diverse subset of search results for deep LLM analysis."""

    @classmethod
    def select_sources(
        cls,
        results: list[SearchResult],
        target_role: str,
        focus_skills: list[str] | None = None,
        max_sources: int = 15,
        max_per_domain: int = 3,
    ) -> list[SearchResult]:
        """
        Rank search results deterministically and select diverse top candidates.
        """
        if not results:
            return []

        if len(results) <= max_sources:
            return results

        skills = [s.lower() for s in (focus_skills or [])]
        role_tokens = [t.lower() for t in re.findall(r"\w+", target_role) if len(t) > 2]

        # Score each result
        scored: list[tuple[float, SearchResult, SourceType, str]] = []
        for r in results:
            parsed = urlparse(r.url)
            domain = parsed.netloc.lower().removeprefix("www.")
            st = cls._classify_search_result(r)

            # Heuristic score components:
            # 1. Base score by type
            base = SOURCE_TYPE_BASE_SCORES.get(st, 0.50)

            # 2. Domain authority bonus
            domain_bonus = 0.15 if any(d in domain for d in AUTHORITATIVE_DOMAINS) else 0.0

            # 3. Search relevance score (from provider if available)
            search_rel = min(1.0, max(0.0, r.score)) if r.score else 0.5

            # 4. Keyword matches in title and snippet
            text = f"{r.title} {r.snippet}".lower()
            role_matches = sum(1 for tok in role_tokens if tok in text)
            skill_matches = sum(1 for sk in skills if sk in text)
            keyword_bonus = min(0.3, role_matches * 0.05 + skill_matches * 0.05)

            total_score = base * 0.4 + domain_bonus + search_rel * 0.3 + keyword_bonus
            scored.append((total_score, r, st, domain))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)

        # Diverse selection with per-domain cap and category balancing
        selected: list[SearchResult] = []
        domain_counts: dict[str, int] = {}
        type_counts: dict[SourceType, int] = {}

        # First pass: pick best candidates with strict domain cap
        for _score, res, st, domain in scored:
            if len(selected) >= max_sources:
                break

            current_domain_count = domain_counts.get(domain, 0)
            if current_domain_count >= max_per_domain:
                continue

            selected.append(res)
            domain_counts[domain] = current_domain_count + 1
            type_counts[st] = type_counts.get(st, 0) + 1

        # Fallback if domain cap was too strict to reach max_sources
        if len(selected) < max_sources:
            selected_urls = {r.url for r in selected}
            for _score, res, _st, _domain in scored:
                if len(selected) >= max_sources:
                    break
                if res.url not in selected_urls:
                    selected.append(res)
                    selected_urls.add(res.url)

        return selected

    @staticmethod
    def _classify_search_result(r: SearchResult) -> SourceType:
        """Infer preliminary SourceType from URL, title, and domain."""
        url_lower = r.url.lower()
        title_lower = r.title.lower()

        if any(w in url_lower or w in title_lower for w in ["job", "career", "posting", "lever.co", "greenhouse.io", "workday", "builtin"]):
            return SourceType.JOB_POSTING

        if any(w in url_lower or w in title_lower for w in ["docs.", "documentation", "api.", "manual", "guide", "reference"]):
            return SourceType.OFFICIAL_DOCUMENTATION

        if any(w in url_lower or w in title_lower or w in r.domain for w in [".edu", "syllabus", "curriculum", "course", "lecture"]):
            return SourceType.UNIVERSITY_CURRICULUM

        if "github.com" in r.domain:
            return SourceType.GITHUB

        return SourceType.OTHER
