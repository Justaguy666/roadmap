"""SQLAlchemy repositories for Research: Source, Evidence, ResearchRun, Recommendation."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from roadmap.domain.entities.source import Evidence, Recommendation, ResearchRun, Source
from roadmap.domain.value_objects import SourceType
from roadmap.storage.models.progress_model import SourceModel
from roadmap.storage.models.research_model import (
    EvidenceModel,
    RecommendationModel,
    ResearchRunModel,
)


class SqliteSourceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, source: Source) -> None:
        existing = self._session.get(SourceModel, source.id)
        if existing:
            existing.title = source.title
            existing.source_type = source.source_type.value
            existing.publisher = source.publisher
            existing.domain = source.domain
            existing.reliability_score = source.reliability_score
            existing.published_at = source.published_at
            existing.content_hash = source.content_hash
        else:
            m = SourceModel(
                id=source.id,
                url=source.url,
                title=source.title,
                source_type=source.source_type.value,
                publisher=source.publisher,
                domain=source.domain,
                retrieved_at=source.retrieved_at,
                published_at=source.published_at,
                reliability_score=source.reliability_score,
                content_hash=source.content_hash,
            )
            self._session.add(m)
        self._session.flush()

    def get_by_id(self, source_id: str) -> Source | None:
        m = self._session.get(SourceModel, source_id)
        if not m:
            return None
        return self._to_entity(m)

    def get_by_url(self, url: str) -> Source | None:
        m = self._session.query(SourceModel).filter(SourceModel.url == url).first()
        if not m:
            return None
        return self._to_entity(m)

    def load_by_url(self, url: str) -> Source | None:
        return self.get_by_url(url)

    def list_all(self, limit: int = 100) -> list[Source]:
        models = self._session.query(SourceModel).limit(limit).all()
        return [self._to_entity(m) for m in models]

    def load_all(self, profile_id: str | None = None) -> list[Source]:
        return self.list_all(limit=1000)

    def _to_entity(self, m: SourceModel) -> Source:
        # Resolve source_type safely
        st = SourceType.OTHER
        try:
            st = SourceType(m.source_type)
        except ValueError:
            st = SourceType.OTHER

        return Source(
            id=m.id,
            url=m.url,
            title=m.title,
            source_type=st,
            publisher=m.publisher,
            domain=m.domain,
            retrieved_at=m.retrieved_at,
            published_at=m.published_at,
            reliability_score=m.reliability_score,
            content_hash=m.content_hash,
        )


class SqliteEvidenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, evidence: Evidence) -> None:
        existing = self._session.get(EvidenceModel, evidence.id)
        if existing:
            existing.extracted_claim = evidence.extracted_claim
            existing.relevance = evidence.relevance
            existing.confidence = evidence.confidence
            existing.associated_skill_names_json = json.dumps(evidence.associated_skill_names)
        else:
            m = EvidenceModel(
                id=evidence.id,
                source_id=evidence.source_id,
                extracted_claim=evidence.extracted_claim,
                relevance=evidence.relevance,
                confidence=evidence.confidence,
                associated_skill_names_json=json.dumps(evidence.associated_skill_names),
                created_at=evidence.created_at,
            )
            self._session.add(m)
        self._session.flush()

    def get_by_id(self, evidence_id: str) -> Evidence | None:
        m = self._session.get(EvidenceModel, evidence_id)
        if not m:
            return None
        return self._to_entity(m)

    def find_by_skill(self, skill_name: str) -> list[Evidence]:
        all_ev = self._session.query(EvidenceModel).all()
        result = []
        for m in all_ev:
            skills = [s.lower() for s in json.loads(m.associated_skill_names_json)]
            if skill_name.lower() in skills:
                result.append(self._to_entity(m))
        return result

    def load_for_skill(self, skill_id: str) -> list[Evidence]:
        return self.find_by_skill(skill_id)

    def load_for_recommendation(self, recommendation_id: str) -> list[Evidence]:
        rec = self._session.get(RecommendationModel, recommendation_id)
        if not rec:
            return []
        eids = json.loads(rec.evidence_ids_json)
        if not eids:
            return []
        models = self._session.query(EvidenceModel).filter(EvidenceModel.id.in_(eids)).all()
        return [self._to_entity(m) for m in models]

    def list_all(self, limit: int = 100) -> list[Evidence]:
        models = self._session.query(EvidenceModel).limit(limit).all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, m: EvidenceModel) -> Evidence:
        return Evidence(
            id=m.id,
            source_id=m.source_id,
            extracted_claim=m.extracted_claim,
            relevance=m.relevance,
            confidence=m.confidence,
            associated_skill_names=json.loads(m.associated_skill_names_json),
            created_at=m.created_at,
        )


class SqliteResearchRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, run: ResearchRun) -> None:
        existing = self._session.get(ResearchRunModel, run.id)
        if existing:
            existing.status = run.status
            existing.source_count = run.source_count
            existing.evidence_count = run.evidence_count
            existing.queries_json = json.dumps(run.queries)
            existing.errors_json = json.dumps(run.errors)
            existing.completed_at = run.completed_at
        else:
            m = ResearchRunModel(
                id=run.id,
                profile_id=run.profile_id,
                topic=run.topic,
                target_market=run.target_market,
                status=run.status,
                source_count=run.source_count,
                evidence_count=run.evidence_count,
                queries_json=json.dumps(run.queries),
                errors_json=json.dumps(run.errors),
                started_at=run.started_at,
                completed_at=run.completed_at,
            )
            self._session.add(m)
        self._session.flush()

    def get_latest(self, profile_id: str | None = None) -> ResearchRun | None:
        q = self._session.query(ResearchRunModel)
        if profile_id:
            q = q.filter(ResearchRunModel.profile_id == profile_id)
        m = q.order_by(ResearchRunModel.started_at.desc()).first()
        if not m:
            return None
        return self._to_entity(m)

    def get_by_id(self, run_id: str) -> ResearchRun | None:
        m = self._session.get(ResearchRunModel, run_id)
        if not m:
            return None
        return self._to_entity(m)

    def _to_entity(self, m: ResearchRunModel) -> ResearchRun:
        return ResearchRun(
            id=m.id,
            profile_id=m.profile_id,
            topic=m.topic,
            target_market=m.target_market,
            status=m.status,
            source_count=m.source_count,
            evidence_count=m.evidence_count,
            queries=json.loads(m.queries_json),
            errors=json.loads(m.errors_json),
            started_at=m.started_at,
            completed_at=m.completed_at,
        )


class SqliteRecommendationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, rec: Recommendation) -> None:
        existing = self._session.get(RecommendationModel, rec.id)
        if existing:
            existing.decision = rec.decision
            existing.reasoning = rec.reasoning
            existing.decision_factors_json = json.dumps(rec.decision_factors)
            existing.evidence_ids_json = json.dumps(rec.evidence_ids)
            existing.confidence = rec.confidence
        else:
            m = RecommendationModel(
                id=rec.id,
                skill_id=rec.skill_id,
                roadmap_id=rec.roadmap_id,
                decision=rec.decision,
                reasoning=rec.reasoning,
                decision_factors_json=json.dumps(rec.decision_factors),
                evidence_ids_json=json.dumps(rec.evidence_ids),
                confidence=rec.confidence,
                created_at=rec.created_at,
            )
            self._session.add(m)
        self._session.flush()

    def find_by_skill(self, skill_id: str) -> list[Recommendation]:
        models = (
            self._session.query(RecommendationModel)
            .filter(RecommendationModel.skill_id == skill_id)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def load_for_skill(self, skill_id: str, roadmap_id: str) -> Recommendation | None:
        m = (
            self._session.query(RecommendationModel)
            .filter(
                RecommendationModel.skill_id == skill_id,
                RecommendationModel.roadmap_id == roadmap_id,
            )
            .first()
        )
        return self._to_entity(m) if m else None

    def find_by_skill_name_or_id(self, skill_name_or_id: str, roadmap_id: str | None = None) -> Recommendation | None:
        q = self._session.query(RecommendationModel).filter(
            (RecommendationModel.skill_id == skill_name_or_id)
            | (RecommendationModel.reasoning.ilike(f"%{skill_name_or_id}%"))
        )
        if roadmap_id:
            q = q.filter(RecommendationModel.roadmap_id == roadmap_id)
        m = q.order_by(RecommendationModel.created_at.desc()).first()
        return self._to_entity(m) if m else None

    def list_by_roadmap(self, roadmap_id: str) -> list[Recommendation]:
        models = (
            self._session.query(RecommendationModel)
            .filter(RecommendationModel.roadmap_id == roadmap_id)
            .all()
        )
        return [self._to_entity(m) for m in models]

    def load_for_roadmap(self, roadmap_id: str) -> list[Recommendation]:
        return self.list_by_roadmap(roadmap_id)

    def _to_entity(self, m: RecommendationModel) -> Recommendation:
        return Recommendation(
            id=m.id,
            skill_id=m.skill_id,
            roadmap_id=m.roadmap_id,
            decision=m.decision,
            reasoning=m.reasoning,
            decision_factors=json.loads(m.decision_factors_json),
            evidence_ids=json.loads(m.evidence_ids_json),
            confidence=m.confidence,
            created_at=m.created_at,
        )
