"""
FastAPI dependency providers for RoadmapAI API (MVP-7.2).

All providers reuse the existing application-layer infrastructure:
  - get_session_factory() / get_engine() from storage.database
  - Sqlite*Repository from storage.repositories
  - Application use cases from application.use_cases / application.services

Route handlers MUST depend on these functions via FastAPI Depends().
Route handlers MUST NOT import Sqlite*Repository or SQLAlchemy models directly.

Authentication: NOT YET IMPLEMENTED — deferred to MVP-7.3.
"""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from roadmap.application.ports.embedding_provider import EmbeddingProvider
from roadmap.application.ports.llm_provider import LLMProvider
from roadmap.application.services.context_builder import EvidenceContextBuilder
from roadmap.application.services.knowledge_indexing_service import KnowledgeIndexingService
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.application.services.rag_service import RAGService
from roadmap.application.services.semantic_retrieval_service import SemanticRetrievalService
from roadmap.application.use_cases.adapt_roadmap import AdaptRoadmapUseCase
from roadmap.application.use_cases.profile_use_cases import (
    CreateProfileUseCase,
    GetProfileUseCase,
)
from roadmap.application.use_cases.record_feedback import RecordFeedbackUseCase
from roadmap.application.use_cases.record_progress import (
    ListProgressUseCase,
    UpdateProgressUseCase,
)
from roadmap.application.use_cases.roadmap_use_cases import (
    GetLatestRoadmapUseCase,
    GetRoadmapByVersionUseCase,
    ListRoadmapsUseCase,
)
from roadmap.infrastructure.vector_store.sqlite_vector_store import SqliteVectorStore
from roadmap.storage.database import get_session_factory
from roadmap.storage.repositories.adaptation_repository import SqliteAdaptationRepository
from roadmap.storage.repositories.feedback_repository import SqliteFeedbackRepository
from roadmap.storage.repositories.knowledge_repository import SqliteKnowledgeRepository
from roadmap.storage.repositories.llm_usage_repository import SqliteLLMUsageRepository
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.progress_repository import SqliteProgressRepository
from roadmap.storage.repositories.research_repository import (
    SqliteEvidenceRepository,
    SqliteSourceRepository,
)
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def get_db_session() -> Generator[Session, None, None]:
    """
    Yield a request-scoped SQLAlchemy session.

    - Commits on success.
    - Rolls back on any exception.
    - Always closes the session.
    - Reuses the existing engine singleton from storage.database — no second engine.
    """
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Repository providers
# ---------------------------------------------------------------------------

def get_profile_repo(session: Session = Depends(get_db_session)) -> SqliteProfileRepository:
    return SqliteProfileRepository(session)


def get_roadmap_repo(session: Session = Depends(get_db_session)) -> SqliteRoadmapRepository:
    return SqliteRoadmapRepository(session)


def get_progress_repo(session: Session = Depends(get_db_session)) -> SqliteProgressRepository:
    return SqliteProgressRepository(session)


def get_feedback_repo(session: Session = Depends(get_db_session)) -> SqliteFeedbackRepository:
    return SqliteFeedbackRepository(session)


def get_adaptation_repo(session: Session = Depends(get_db_session)) -> SqliteAdaptationRepository:
    return SqliteAdaptationRepository(session)


def get_usage_repo(session: Session = Depends(get_db_session)) -> SqliteLLMUsageRepository:
    return SqliteLLMUsageRepository(session)


def get_evidence_repo(session: Session = Depends(get_db_session)) -> SqliteEvidenceRepository:
    return SqliteEvidenceRepository(session)


def get_source_repo(session: Session = Depends(get_db_session)) -> SqliteSourceRepository:
    return SqliteSourceRepository(session)


def get_knowledge_repo(session: Session = Depends(get_db_session)) -> SqliteKnowledgeRepository:
    return SqliteKnowledgeRepository(session)


# ---------------------------------------------------------------------------
# Service / use-case providers
# ---------------------------------------------------------------------------

def get_budget_manager(
    usage_repo: SqliteLLMUsageRepository = Depends(get_usage_repo),
) -> LLMBudgetManager:
    return LLMBudgetManager(repository=usage_repo)


def get_create_profile_use_case(
    profile_repo: SqliteProfileRepository = Depends(get_profile_repo),
) -> CreateProfileUseCase:
    return CreateProfileUseCase(profile_repo=profile_repo)


def get_get_profile_use_case(
    profile_repo: SqliteProfileRepository = Depends(get_profile_repo),
) -> GetProfileUseCase:
    return GetProfileUseCase(profile_repo=profile_repo)


def get_record_progress_use_case(
    roadmap_repo: SqliteRoadmapRepository = Depends(get_roadmap_repo),
    progress_repo: SqliteProgressRepository = Depends(get_progress_repo),
    feedback_repo: SqliteFeedbackRepository = Depends(get_feedback_repo),
) -> UpdateProgressUseCase:
    return UpdateProgressUseCase(
        roadmap_repo=roadmap_repo,
        progress_repo=progress_repo,
        feedback_repo=feedback_repo,
    )


def get_record_feedback_use_case(
    roadmap_repo: SqliteRoadmapRepository = Depends(get_roadmap_repo),
    feedback_repo: SqliteFeedbackRepository = Depends(get_feedback_repo),
) -> RecordFeedbackUseCase:
    return RecordFeedbackUseCase(
        roadmap_repo=roadmap_repo,
        feedback_repo=feedback_repo,
    )


def get_list_roadmaps_use_case(
    roadmap_repo: SqliteRoadmapRepository = Depends(get_roadmap_repo),
) -> ListRoadmapsUseCase:
    return ListRoadmapsUseCase(roadmap_repo=roadmap_repo)


def get_get_latest_roadmap_use_case(
    roadmap_repo: SqliteRoadmapRepository = Depends(get_roadmap_repo),
) -> GetLatestRoadmapUseCase:
    return GetLatestRoadmapUseCase(roadmap_repo=roadmap_repo)


def get_get_roadmap_by_version_use_case(
    roadmap_repo: SqliteRoadmapRepository = Depends(get_roadmap_repo),
) -> GetRoadmapByVersionUseCase:
    return GetRoadmapByVersionUseCase(roadmap_repo=roadmap_repo)


def get_list_progress_use_case(
    progress_repo: SqliteProgressRepository = Depends(get_progress_repo),
) -> ListProgressUseCase:
    return ListProgressUseCase(progress_repo=progress_repo)


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider (reuses CLI container logic)."""
    from roadmap.cli.container import get_llm_provider as _get_llm_provider

    return _get_llm_provider()


def get_adapt_roadmap_use_case(
    roadmap_repo: SqliteRoadmapRepository = Depends(get_roadmap_repo),
    progress_repo: SqliteProgressRepository = Depends(get_progress_repo),
    feedback_repo: SqliteFeedbackRepository = Depends(get_feedback_repo),
    adaptation_repo: SqliteAdaptationRepository = Depends(get_adaptation_repo),
    budget_manager: LLMBudgetManager = Depends(get_budget_manager),
) -> AdaptRoadmapUseCase:
    from roadmap.agents.adaptation_agent import AdaptationAgent

    llm = get_llm_provider()
    agent = AdaptationAgent(llm_provider=llm, budget_manager=budget_manager)
    return AdaptRoadmapUseCase(
        roadmap_repo=roadmap_repo,
        progress_repo=progress_repo,
        feedback_repo=feedback_repo,
        adaptation_repo=adaptation_repo,
        adaptation_agent=agent,
    )


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider (reuses CLI container logic)."""
    from roadmap.cli.container import get_embedding_provider as _get_emb

    return _get_emb()


def get_rag_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> RAGService:
    """
    Build RAGService wired to the request session.

    Does NOT call the LLM — only semantic vector retrieval + context building.
    Preserves all evidence provenance (evidence_id, source_id, source_url).
    """
    evidence_repo = SqliteEvidenceRepository(session)
    source_repo = SqliteSourceRepository(session)
    vector_store = SqliteVectorStore(session)

    retrieval_service = SemanticRetrievalService(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        evidence_repo=evidence_repo,
        source_repo=source_repo,
    )
    context_builder = EvidenceContextBuilder(
        evidence_repo=evidence_repo,
        source_repo=source_repo,
    )
    return RAGService(
        retrieval_service=retrieval_service,
        context_builder=context_builder,
    )


def get_knowledge_indexing_service(
    session: Session = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> KnowledgeIndexingService:
    """Build KnowledgeIndexingService wired to the request session."""
    return KnowledgeIndexingService(
        evidence_repo=SqliteEvidenceRepository(session),
        source_repo=SqliteSourceRepository(session),
        knowledge_repo=SqliteKnowledgeRepository(session),
        embedding_provider=embedding_provider,
    )

