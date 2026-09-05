"""
ResearchService: Orchestrates web search, URL deduplication, fetching,
LLM evidence extraction, deterministic source scoring, and sample calculation.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from urllib.parse import urlparse

from roadmap.agents.prompts.research import (
    EVIDENCE_EXTRACTION_SYSTEM_PROMPT,
    RESEARCH_PLAN_SYSTEM_PROMPT,
    build_evidence_extraction_prompt,
    build_research_plan_prompt,
)
from roadmap.agents.schemas.research import (
    EvidenceExtractionResult,
    MarketResearchResult,
    MarketSkillObservation,
    RecommendedResourceDraft,
    ResearchPlan,
    ResourceResearchResult,
)
from roadmap.application.ports.infrastructure import Cache, WebFetcher
from roadmap.application.ports.llm_provider import LLMMessage, LLMProvider
from roadmap.application.ports.search_provider import SearchProvider, SearchResult
from roadmap.config.settings import settings
from roadmap.domain.entities.source import Evidence, ResearchRun, Source
from roadmap.domain.services.source_scorer import SourceScorer
from roadmap.domain.services.url_normalizer import normalize_url
from roadmap.domain.value_objects import SourceType
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteResearchRunRepository,
    SqliteSourceRepository,
)

logger = get_logger(__name__)


class ResearchService:
    """End-to-end research orchestration service."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        search_provider: SearchProvider,
        web_fetcher: WebFetcher,
        cache: Cache,
        source_repo: SqliteSourceRepository,
        evidence_repo: SqliteEvidenceRepository,
        run_repo: SqliteResearchRunRepository,
        concurrency: int = 5,
    ) -> None:
        self.llm = llm_provider
        self.search_provider = search_provider
        self.web_fetcher = web_fetcher
        self.cache = cache
        self.source_repo = source_repo
        self.evidence_repo = evidence_repo
        self.run_repo = run_repo
        self.concurrency = concurrency

    def execute_research(
        self,
        profile_id: str,
        topic: str,
        target_market: str = "",
        focus_skills: list[str] | None = None,
        include_market: bool = True,
        include_resources: bool = True,
        force_refresh: bool = False,
        progress_callback: Callable[[str], None] | None = None,
    ) -> tuple[ResearchRun, MarketResearchResult, ResourceResearchResult]:
        """
        Execute full research run:
        1. Plan search queries via LLM
        2. Query search provider with cache
        3. Deduplicate URLs
        4. Fetch pages with bounded concurrency
        5. Extract claims & evidence via LLM
        6. Score sources deterministically
        7. Persist sources, evidence, and research run
        8. Compute market sample statistics and return results
        """
        def notify(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        run = ResearchRun(
            profile_id=profile_id,
            topic=topic,
            target_market=target_market,
            status="running",
            started_at=datetime.now(UTC),
        )
        self.run_repo.save(run)

        # 1. Plan queries
        notify("Formulating research plan...")
        plan_user_prompt = build_research_plan_prompt(
            topic=topic,
            target_market=target_market,
            focus_skills=focus_skills,
        )
        plan_messages = [
            LLMMessage(role="system", content=RESEARCH_PLAN_SYSTEM_PROMPT),
            LLMMessage(role="user", content=plan_user_prompt),
        ]
        plan: ResearchPlan = self.llm.complete(
            messages=plan_messages,
            response_model=ResearchPlan,
            temperature=0.2,
        )

        filtered_queries = [
            q for q in plan.queries
            if (q.query_type == "market" and include_market)
            or (q.query_type == "resource" and include_resources)
            or (q.query_type not in ("market", "resource"))
        ]
        if not filtered_queries:
            filtered_queries = plan.queries

        run.queries = [q.query for q in filtered_queries]
        self.run_repo.save(run)

        # 2. Search
        notify(f"Executing {len(filtered_queries)} targeted search queries...")
        raw_results: list[SearchResult] = []
        errors: list[str] = []

        for q in filtered_queries:
            cache_key = f"search:{self.search_provider.__class__.__name__}:{q.query}"
            if not force_refresh and self.cache.exists(cache_key):
                cached_data = self.cache.get(cache_key)
                if cached_data:
                    try:
                        items = json.loads(cached_data.decode("utf-8"))
                        for item in items:
                            raw_results.append(
                                SearchResult(
                                    url=item["url"],
                                    title=item["title"],
                                    snippet=item.get("snippet", ""),
                                    domain=item.get("domain", ""),
                                    score=item.get("score", 0.0),
                                    content=item.get("content", ""),
                                )
                            )
                        continue
                    except Exception:
                        pass

            try:
                resp = self.search_provider.search(
                    query=q.query,
                    max_results=settings.search_max_results,
                    include_full_content=False,
                )
                raw_results.extend(resp.results)
                serializable = [
                    {
                        "url": r.url,
                        "title": r.title,
                        "snippet": r.snippet,
                        "domain": r.domain,
                        "score": r.score,
                        "content": r.content,
                    }
                    for r in resp.results
                ]
                self.cache.set(
                    cache_key,
                    json.dumps(serializable).encode("utf-8"),
                    ttl_seconds=settings.cache_ttl_hours * 3600,
                )
            except Exception as exc:
                err_msg = f"Search failed for '{q.query}': {exc}"
                logger.warning(err_msg)
                errors.append(err_msg)

        # 3. Deduplicate URLs
        notify("Deduplicating retrieved sources...")
        deduped_results: dict[str, SearchResult] = {}
        for r in raw_results:
            canon = normalize_url(r.url)
            if canon and canon not in deduped_results:
                deduped_results[canon] = r

        notify(f"Discovered {len(deduped_results)} unique sources. Fetching readable content...")

        # 4. Fetch content concurrently
        fetched_pages: dict[str, tuple[SearchResult, str]] = {}
        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(deduped_results) or 1)) as executor:
            future_to_url = {
                executor.submit(self._fetch_single_page, url, res): url
                for url, res in deduped_results.items()
            }
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    res, text = future.result()
                    if text:
                        fetched_pages[url] = (res, text)
                except Exception as exc:
                    err = f"Failed to fetch {url}: {exc}"
                    logger.debug(err)
                    errors.append(err)

        # 5. Extract claims and build sources/evidence
        notify(f"Analyzing {len(fetched_pages)} pages and extracting evidence...")
        saved_sources: list[Source] = []
        saved_evidence: list[Evidence] = []
        source_type_counts: dict[str, int] = defaultdict(int)

        for url, (s_res, text) in fetched_pages.items():
            source = self.source_repo.get_by_url(url)
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            if not source:
                domain = urlparse(url).netloc
                source = Source(
                    id=new_id(),
                    url=url,
                    title=s_res.title,
                    domain=domain,
                    source_type=SourceType.OTHER,
                    content_hash=content_hash,
                )

            ext_prompt = build_evidence_extraction_prompt(
                url=url,
                title=s_res.title,
                text_content=text,
                target_goal=topic,
            )
            ext_messages = [
                LLMMessage(role="system", content=EVIDENCE_EXTRACTION_SYSTEM_PROMPT),
                LLMMessage(role="user", content=ext_prompt),
            ]

            try:
                extraction: EvidenceExtractionResult = self.llm.complete(
                    messages=ext_messages,
                    response_model=EvidenceExtractionResult,
                    temperature=0.1,
                )
            except Exception as exc:
                errors.append(f"Evidence extraction failed for {url}: {exc}")
                continue

            detected_type = extraction.detected_source_type.lower().strip()
            for st in SourceType:
                if st.value == detected_type:
                    source.source_type = st
                    break

            source.reliability_score = SourceScorer.score(source)
            self.source_repo.save(source)
            saved_sources.append(source)
            source_type_counts[source.source_type.value] += 1

            for claim_draft in extraction.claims:
                ev = Evidence(
                    id=new_id(),
                    source_id=source.id,
                    extracted_claim=claim_draft.claim,
                    relevance=claim_draft.relevance,
                    confidence=claim_draft.confidence,
                    associated_skill_names=claim_draft.related_skills,
                )
                self.evidence_repo.save(ev)
                saved_evidence.append(ev)

        # 6. Compute Market Statistics (Observed sample)
        skill_mentions: dict[str, list[str]] = defaultdict(list)
        job_postings_sample_count = source_type_counts.get("job_posting", 0) + source_type_counts.get("company_career_page", 0)
        effective_sample_size = max(1, job_postings_sample_count or len(saved_sources))

        for ev in saved_evidence:
            for sk_name in ev.associated_skill_names:
                skill_norm = sk_name.strip()
                skill_mentions[skill_norm].append(ev.id)

        skill_observations: list[MarketSkillObservation] = []
        for skill_name, ev_ids in skill_mentions.items():
            unique_ev_ids = list(dict.fromkeys(ev_ids))
            mentions = min(len(unique_ev_ids), effective_sample_size)
            freq = round(mentions / effective_sample_size, 2)
            skill_observations.append(
                MarketSkillObservation(
                    skill_name=skill_name,
                    sample_size=effective_sample_size,
                    mentions=mentions,
                    observed_frequency=freq,
                    supporting_evidence_ids=unique_ev_ids[:5],
                )
            )

        skill_observations.sort(key=lambda o: (o.observed_frequency, o.mentions), reverse=True)

        market_result = MarketResearchResult(
            target_role=topic,
            target_market=target_market,
            total_postings_sampled=effective_sample_size,
            key_findings=[
                f"Sampled {effective_sample_size} postings/pages for {topic}.",
                f"Extracted {len(saved_evidence)} verified claims across {len(saved_sources)} sources.",
            ],
            skill_observations=skill_observations,
        )

        # 7. Build Resource Recommendations
        resource_drafts: list[RecommendedResourceDraft] = []
        for src in saved_sources:
            if src.source_type in (
                SourceType.OFFICIAL_DOCUMENTATION,
                SourceType.OFFICIAL_DOCS,
                SourceType.UNIVERSITY_CURRICULUM,
                SourceType.UNIVERSITY,
                SourceType.COURSE,
                SourceType.BOOK,
                SourceType.GITHUB,
            ):
                matching_ev = [e for e in saved_evidence if e.source_id == src.id]
                rel_skill = (
                    matching_ev[0].associated_skill_names[0]
                    if matching_ev and matching_ev[0].associated_skill_names
                    else "Core Engineering"
                )
                res_type = (
                    "docs"
                    if "docs" in src.source_type.value
                    else ("course" if "course" in src.source_type.value or "univ" in src.source_type.value else "book")
                )
                resource_drafts.append(
                    RecommendedResourceDraft(
                        title=src.title or src.domain,
                        url=src.url,
                        provider=src.publisher or src.domain,
                        resource_type=res_type,
                        difficulty="familiar",
                        related_skill=rel_skill,
                        rationale=matching_ev[0].extracted_claim if matching_ev else "Authoritative documentation or reference",
                        estimated_hours=15.0,
                    )
                )

        resource_result = ResourceResearchResult(
            target_skills=list(skill_mentions.keys())[:10],
            resources=resource_drafts,
        )

        # 8. Complete and persist research run
        run.status = "completed" if saved_sources else ("partial" if errors else "failed")
        run.source_count = len(saved_sources)
        run.evidence_count = len(saved_evidence)
        run.errors = errors
        run.completed_at = datetime.now(UTC)
        self.run_repo.save(run)

        notify(f"Research complete: {run.source_count} sources, {run.evidence_count} evidence items saved.")
        return run, market_result, resource_result

    def _fetch_single_page(self, url: str, search_res: SearchResult) -> tuple[SearchResult, str]:
        """Fetch readable content from WebFetcher or use snippet if fetch fails."""
        try:
            fetch_res = self.web_fetcher.fetch(url, timeout=20)
            if fetch_res.is_success and fetch_res.content:
                return search_res, fetch_res.content
        except Exception:
            pass

        fallback = search_res.content or search_res.snippet
        return search_res, fallback
