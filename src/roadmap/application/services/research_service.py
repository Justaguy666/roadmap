"""
ResearchService: Orchestrates web search, deterministic source selection,
caching, fetching, batched LLM evidence extraction with rate-limiting,
deterministic source scoring, and sample calculation.
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
    BATCH_EVIDENCE_EXTRACTION_SYSTEM_PROMPT,
    RESEARCH_PLAN_SYSTEM_PROMPT,
    build_batch_evidence_extraction_prompt,
    build_research_plan_prompt,
)
from roadmap.agents.schemas.research import (
    BatchEvidenceExtractionResult,
    ExtractedClaimDraft,
    MarketResearchResult,
    MarketSkillObservation,
    RecommendedResourceDraft,
    ResearchPlan,
    ResourceResearchResult,
)
from roadmap.application.ports.infrastructure import Cache, WebFetcher
from roadmap.application.ports.llm_provider import (
    LLMDailyQuotaExceededError,
    LLMMessage,
    LLMProvider,
    LLMRateLimitError,
)
from roadmap.application.ports.search_provider import SearchProvider, SearchResult
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.config.settings import settings
from roadmap.domain.entities.source import Evidence, ResearchRun, Source
from roadmap.domain.services.source_scorer import SourceScorer
from roadmap.domain.services.source_selector import SourceSelector
from roadmap.domain.services.url_normalizer import normalize_url
from roadmap.domain.value_objects import SourceType
from roadmap.domain.value_objects.enums import FailureCategory, LLMWorkflow
from roadmap.infrastructure.llm.rate_limiter import RateLimiter
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteResearchRunRepository,
    SqliteSourceRepository,
)

logger = get_logger(__name__)


class ResearchService:
    """End-to-end research orchestration service with batch extraction and quota management."""

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
        rate_limiter: RateLimiter | None = None,
        budget_manager: LLMBudgetManager | None = None,
    ) -> None:
        self.llm = llm_provider
        self.search_provider = search_provider
        self.web_fetcher = web_fetcher
        self.cache = cache
        self.source_repo = source_repo
        self.evidence_repo = evidence_repo
        self.run_repo = run_repo
        self.concurrency = concurrency
        self.rate_limiter = rate_limiter or RateLimiter(
            requests_per_minute=settings.llm_requests_per_minute
        )
        self.budget_manager = budget_manager

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
        1. Plan search queries via LLM (rate-limited)
        2. Query search provider with cache
        3. Deduplicate URLs
        4. Deterministic source ranking and diversity selection (budget capped)
        5. Fetch pages with bounded concurrency
        6. Batch extract claims & evidence via LLM (rate-limited, quota-aware)
        7. Score sources deterministically
        8. Persist sources, evidence, and research run
        9. Compute market sample statistics and return results
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
        errors: list[str] = []
        plan_user_prompt = build_research_plan_prompt(
            topic=topic,
            target_market=target_market,
            focus_skills=focus_skills,
        )
        plan_messages = [
            LLMMessage(role="system", content=RESEARCH_PLAN_SYSTEM_PROMPT),
            LLMMessage(role="user", content=plan_user_prompt),
        ]

        plan_res = None
        prov_name = getattr(self.llm, "provider_name", settings.llm_provider)
        mod_name = getattr(self.llm, "model_name", settings.llm_model or "default")
        if self.budget_manager:
            try:
                plan_res = self.budget_manager.reserve(
                    workflow=LLMWorkflow.RESEARCH,
                    operation="query_planning",
                    provider=prov_name,
                    model=mod_name,
                    estimated_requests=1,
                    correlation_id=run.id,
                )
            except Exception as b_err:
                err_msg = f"Research budget exhausted before query planning: {b_err}"
                logger.warning(err_msg)
                errors.append(err_msg)
                run.status = "failed"
                run.errors = errors
                run.completed_at = datetime.now(UTC)
                self.run_repo.save(run)
                notify(err_msg)
                return (
                    run,
                    MarketResearchResult(target_role=topic, target_market=target_market, total_postings_sampled=0),
                    ResourceResearchResult(target_skills=[]),
                )

        self.rate_limiter.acquire()
        try:
            plan: ResearchPlan = self.llm.complete(
                messages=plan_messages,
                response_model=ResearchPlan,
                temperature=0.2,
            )
            if self.budget_manager and plan_res:
                self.budget_manager.commit(
                    reservation=plan_res,
                    success=True,
                    actual_requests=1,
                )
        except LLMDailyQuotaExceededError as qe:
            err_msg = f"Gemini daily quota exhausted during research planning: {qe}"
            logger.error(err_msg)
            if self.budget_manager and plan_res:
                self.budget_manager.commit(
                    reservation=plan_res,
                    success=False,
                    failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED,
                    actual_requests=1,
                    error_message=str(qe),
                )
            run.status = "failed"
            run.errors = [err_msg]
            run.completed_at = datetime.now(UTC)
            self.run_repo.save(run)
            notify("DAILY_QUOTA_EXCEEDED: Gemini quota exhausted.")
            return (
                run,
                MarketResearchResult(target_role=topic, target_market=target_market, total_postings_sampled=0),
                ResourceResearchResult(target_skills=[]),
            )
        except Exception as e:
            logger.warning("Research planning failed, using fallback query list", error=str(e))
            if self.budget_manager and plan_res:
                fc = getattr(e, "failure_category", FailureCategory.UNKNOWN_PROVIDER_ERROR)
                self.budget_manager.commit(
                    reservation=plan_res,
                    success=False,
                    failure_category=fc,
                    actual_requests=1,
                    error_message=str(e),
                )
            plan = ResearchPlan(
                topic=topic,
                target_market=target_market,
                queries=[],
            )

        filtered_queries = [
            q for q in plan.queries
            if (q.query_type == "market" and include_market)
            or (q.query_type == "resource" and include_resources)
            or (q.query_type not in ("market", "resource"))
        ]
        if not filtered_queries:
            # Generate deterministic fallback queries with target_market
            market_suffix = f" {target_market}" if target_market else ""
            from roadmap.agents.schemas.research import ResearchQuery

            filtered_queries = [
                ResearchQuery(query=f"{topic} requirements{market_suffix}", query_type="market", focus=topic),
                ResearchQuery(query=f"{topic} skills job posting{market_suffix}", query_type="market", focus=topic),
                ResearchQuery(query=f"{topic} documentation curriculum tutorial", query_type="resource", focus=topic),
            ]

        run.queries = [q.query for q in filtered_queries]
        self.run_repo.save(run)

        # 2. Search
        notify(f"Executing {len(filtered_queries)} targeted search queries...")
        raw_results: list[SearchResult] = []

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

        total_discovered = len(deduped_results)
        max_source_budget = settings.research_max_sources

        # 4. Deterministic Source Ranking & Diversity Selection
        selected_search_results = SourceSelector.select_sources(
            results=list(deduped_results.values()),
            target_role=topic,
            focus_skills=focus_skills,
            max_sources=max_source_budget,
            max_per_domain=3,
        )

        notify(
            f"Search results found: {total_discovered}  |  "
            f"Deep-analysis budget: {max_source_budget}  |  "
            f"Selected: {len(selected_search_results)}"
        )

        # 5. Fetch content concurrently for selected high-value sources
        notify(f"Fetching readable content for {len(selected_search_results)} sources...")
        fetched_pages: dict[str, tuple[SearchResult, str]] = {}
        with ThreadPoolExecutor(max_workers=min(self.concurrency, len(selected_search_results) or 1)) as executor:
            future_to_res = {
                executor.submit(self._fetch_single_page, res.url, res): res
                for res in selected_search_results
            }
            for future in as_completed(future_to_res):
                res = future_to_res[future]
                try:
                    r, text = future.result()
                    if text:
                        canon_u = normalize_url(r.url)
                        fetched_pages[canon_u] = (r, text)
                except Exception as exc:
                    err = f"Failed to fetch {res.url}: {exc}"
                    logger.debug(err)
                    errors.append(err)

        # 6. Batch LLM Evidence Extraction
        page_list = list(fetched_pages.items())
        batch_size = max(1, settings.research_batch_size)
        batches: list[list[tuple[str, tuple[SearchResult, str]]]] = [
            page_list[i : i + batch_size] for i in range(0, len(page_list), batch_size)
        ]

        # Check and clamp batches against remaining research budget if manager is available
        if self.budget_manager and batches:
            window_start = self.budget_manager._get_window_start()
            wf_used = self.budget_manager.repository.count_requests_since(window_start, workflow=LLMWorkflow.RESEARCH)
            wf_limit = self.budget_manager.workflow_budgets.get(LLMWorkflow.RESEARCH, self.budget_manager.daily_budget)
            remaining_budget = max(0, wf_limit - wf_used)
            if remaining_budget == 0:
                warn_budget = f"Research application budget exhausted ({wf_used}/{wf_limit} used). Skipping deep extraction."
                logger.warning(warn_budget)
                errors.append(warn_budget)
                notify(warn_budget)
                batches = []
            elif len(batches) > remaining_budget:
                notify(
                    f"Clamping extraction batches from {len(batches)} down to remaining research budget ({remaining_budget})..."
                )
                batches = batches[:remaining_budget]

        notify(
            f"Batching {len(page_list)} pages into {len(batches)} extraction batches "
            f"(batch size: {batch_size})..."
        )

        saved_sources: list[Source] = []
        saved_evidence: list[Evidence] = []
        source_type_counts: dict[str, int] = defaultdict(int)
        quota_exhausted: bool = False

        for b_idx, batch in enumerate(batches, start=1):
            if quota_exhausted:
                break

            notify(f"Extracting evidence claims: Batch {b_idx}/{len(batches)} ({len(batch)} pages)...")
            batch_payload: list[tuple[int, str, str, str]] = []
            for item_idx, (url, (s_res, text)) in enumerate(batch):
                bounded_text = text[: settings.research_max_content_chars]
                batch_payload.append((item_idx, url, s_res.title, bounded_text))

            prompt_text = build_batch_evidence_extraction_prompt(
                pages=batch_payload,
                target_goal=topic,
                target_market=target_market,
            )
            batch_messages = [
                LLMMessage(role="system", content=BATCH_EVIDENCE_EXTRACTION_SYSTEM_PROMPT),
                LLMMessage(role="user", content=prompt_text),
            ]

            batch_res = None
            if self.budget_manager:
                try:
                    batch_res = self.budget_manager.reserve(
                        workflow=LLMWorkflow.RESEARCH,
                        operation=f"batch_extraction_{b_idx}",
                        provider=prov_name,
                        model=mod_name,
                        estimated_requests=1,
                        correlation_id=run.id,
                    )
                except Exception as b_err:
                    err_msg = f"Research budget exhausted before batch {b_idx}: {b_err}"
                    logger.warning(err_msg)
                    errors.append(err_msg)
                    notify(err_msg)
                    break

            self.rate_limiter.acquire()
            batch_extraction: BatchEvidenceExtractionResult | None = None

            try:
                batch_extraction = self.llm.complete(
                    messages=batch_messages,
                    response_model=BatchEvidenceExtractionResult,
                    temperature=0.1,
                )
                if self.budget_manager and batch_res:
                    self.budget_manager.commit(
                        reservation=batch_res,
                        success=True,
                        actual_requests=1,
                    )
            except LLMDailyQuotaExceededError as dqe:
                err_msg = f"DAILY_QUOTA_EXCEEDED during batch {b_idx}: {dqe}"
                logger.error(err_msg)
                errors.append(err_msg)
                quota_exhausted = True
                if self.budget_manager and batch_res:
                    self.budget_manager.commit(
                        reservation=batch_res,
                        success=False,
                        failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED,
                        actual_requests=1,
                        error_message=str(dqe),
                    )
                notify("Gemini daily quota exhausted. Stopping further extraction.")
                break
            except LLMRateLimitError as rle:
                # Check for retry after delay
                logger.warning("Rate limit encountered during batch extraction", error=str(rle))
                if rle.retry_after and rle.retry_after < 60:
                    notify(f"Rate limited. Waiting {int(rle.retry_after)}s before retry...")
                    self.rate_limiter.wait_for(rle.retry_after)
                    try:
                        self.rate_limiter.acquire()
                        batch_extraction = self.llm.complete(
                            messages=batch_messages,
                            response_model=BatchEvidenceExtractionResult,
                            temperature=0.1,
                        )
                        if self.budget_manager and batch_res:
                            self.budget_manager.commit(
                                reservation=batch_res,
                                success=True,
                                actual_requests=1,
                            )
                    except Exception as retry_exc:
                        err_msg = f"Batch extraction retry failed: {retry_exc}"
                        logger.error(err_msg)
                        errors.append(err_msg)
                        is_dq = isinstance(retry_exc, LLMDailyQuotaExceededError)
                        if self.budget_manager and batch_res:
                            self.budget_manager.commit(
                                reservation=batch_res,
                                success=False,
                                failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED if is_dq else FailureCategory.PROVIDER_RATE_LIMITED,
                                actual_requests=1,
                                error_message=str(retry_exc),
                            )
                        if is_dq:
                            quota_exhausted = True
                            break
                else:
                    errors.append(f"Rate limit exceeded on batch {b_idx}: {rle}")
                    quota_exhausted = True
                    if self.budget_manager and batch_res:
                        self.budget_manager.commit(
                            reservation=batch_res,
                            success=False,
                            failure_category=FailureCategory.PROVIDER_RATE_LIMITED,
                            actual_requests=1,
                            error_message=str(rle),
                        )
                    break
            except Exception as exc:
                err_msg = f"Batch extraction failed for batch {b_idx}: {exc}"
                logger.error(err_msg)
                errors.append(err_msg)
                if self.budget_manager and batch_res:
                    fc = getattr(exc, "failure_category", FailureCategory.UNKNOWN_PROVIDER_ERROR)
                    self.budget_manager.commit(
                        reservation=batch_res,
                        success=False,
                        failure_category=fc,
                        actual_requests=1,
                        error_message=str(exc),
                    )
                continue

            # Process extracted documents from this batch
            if batch_extraction and batch_extraction.documents:
                # Map extracted results by index or url
                extracted_map: dict[str, tuple[str, list[ExtractedClaimDraft]]] = {}
                for doc in batch_extraction.documents:
                    norm_u = normalize_url(doc.url)
                    extracted_map[norm_u] = (doc.detected_source_type, doc.claims)

                for item_idx, (url, (s_res, text)) in enumerate(batch):
                    norm_u = normalize_url(url)
                    det_type, claims = extracted_map.get(norm_u, ("other", []))

                    # If not matched by URL, check by item_idx
                    if not claims and item_idx < len(batch_extraction.documents):
                        doc = batch_extraction.documents[item_idx]
                        det_type = doc.detected_source_type
                        claims = doc.claims

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

                    detected_clean = det_type.lower().strip()
                    for st in SourceType:
                        if st.value == detected_clean:
                            source.source_type = st
                            break

                    source.reliability_score = SourceScorer.score(source)
                    self.source_repo.save(source)
                    saved_sources.append(source)
                    source_type_counts[source.source_type.value] += 1

                    for claim_draft in claims:
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

        # 7. Compute Market Statistics (Observed sample)
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

        # 8. Build Resource Recommendations
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

        # 9. Determine Status & Persist Run
        target_count = len(selected_search_results)
        if len(saved_sources) == 0 or len(saved_evidence) == 0:
            status = "failed"
        elif quota_exhausted or (target_count > 0 and len(saved_sources) < int(target_count * 0.6)):
            status = "partial"
        else:
            status = "completed"

        run.status = status
        run.source_count = len(saved_sources)
        run.evidence_count = len(saved_evidence)
        run.errors = errors
        run.completed_at = datetime.now(UTC)
        self.run_repo.save(run)

        if status == "partial":
            notify(
                f"Research finished with PARTIAL status: {run.source_count}/{target_count} sources analyzed, "
                f"{run.evidence_count} evidence items saved (quota or rate limit reached)."
            )
        else:
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
