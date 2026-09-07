"""Integration test verifying MVP-4.1 Quality, Evidence and Decision Integrity."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from roadmap.domain.entities.evidence_aggregation import SkillEvidenceSummary
from roadmap.domain.entities.learning_resource import Project
from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.entities.source import Recommendation
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.services.quality_scorer import QualityScorer
from roadmap.domain.value_objects import Priority
from roadmap.storage.models.base import Base
from roadmap.storage.repositories.research_repository import SqliteRecommendationRepository
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository


def test_recommendation_find_by_skill_name_and_id() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        roadmap_repo = SqliteRoadmapRepository(session)
        rec_repo = SqliteRecommendationRepository(session)

        sk = Skill(
            id="skill-cpp-123",
            profile_id="prof-1",
            name="C++ Programming",
            category="Languages",
            priority=Priority.CRITICAL,
            estimated_hours=40.0,
        )
        phase = RoadmapPhase(
            roadmap_id="rm-1",
            phase_number=1,
            name="Phase 1",
            skills=[sk],
            projects=[Project(name="Engine Test")],
        )
        rm = Roadmap(
            id="rm-1",
            profile_id="prof-1",
            title="Game Dev Roadmap",
            phases=[phase],
            validation_status="COMPLETED_WITH_WARNINGS",
            evaluator_score=82.0,
            evaluator_verdict="REVISE",
        )
        roadmap_repo.save(rm)

        rec = Recommendation(
            id="rec-1",
            skill_id=sk.id,
            roadmap_id=rm.id,
            decision="include",
            reasoning="Strong market demand for C++",
            confidence=0.88,
            decision_factors={
                "market_relevance": 0.90,
                "goal_relevance": 0.85,
                "skill_gap": 0.67,
                "prerequisite_importance": 0.25,
                "portfolio_value": 0.85,
                "time_cost_factor": 0.67,
            },
        )
        rec_repo.save(rec)

        found_exact = rec_repo.find_by_skill_name_or_id("C++ Programming", roadmap_id=rm.id)
        assert found_exact is not None
        assert found_exact.id == rec.id
        assert found_exact.decision_factors["market_relevance"] == 0.90

        found_id = rec_repo.find_by_skill_name_or_id(sk.id, roadmap_id=rm.id)
        assert found_id is not None
        assert found_id.id == rec.id

        found_sub = rec_repo.find_by_skill_name_or_id("C++", roadmap_id=rm.id)
        assert found_sub is not None
        assert found_sub.id == rec.id

        loaded_rm = roadmap_repo.load_latest("prof-1")
        assert loaded_rm is not None
        assert loaded_rm.validation_status == "COMPLETED_WITH_WARNINGS"
        assert loaded_rm.evaluator_score == 82.0
        assert loaded_rm.evaluator_verdict == "REVISE"


def test_quality_scorer_fuzzy_evidence_grounding() -> None:
    profile = UserProfile(
        name="Tester",
        target_goal="Game Dev",
        target_role="Gameplay Programmer",
        study_hours_per_day=3.0,
        deadline_months=6,
    )
    sk1 = Skill(profile_id=profile.id, name="Version Control (Git)", estimated_hours=20.0)
    sk2 = Skill(profile_id=profile.id, name="C++ Programming", estimated_hours=40.0)
    phase = RoadmapPhase(
        roadmap_id="rm-2",
        phase_number=1,
        name="Phase 1",
        skills=[sk1, sk2],
        projects=[Project(name="Git Engine")],
    )
    rm = Roadmap(
        id="rm-2",
        profile_id=profile.id,
        title="Test",
        objective="Master game development foundations and core technical competencies",
        phases=[phase],
    )

    summaries = {
        "Version Control": SkillEvidenceSummary(skill_name="Version Control", evidence_count=3, weighted_score=0.85),
        "C++": SkillEvidenceSummary(skill_name="C++", evidence_count=7, weighted_score=0.95),
    }

    score = QualityScorer.calculate_score(rm, profile, summaries)
    assert score.evidence_strength == 100.0
    assert score.market_alignment > 85.0
    assert score.overall_score >= 85.0


def test_quality_scorer_reproducibility() -> None:
    profile = UserProfile(
        name="Tester",
        target_goal="Game Dev",
        target_role="Gameplay Programmer",
        study_hours_per_day=3.0,
        deadline_months=6,
    )
    sk1 = Skill(profile_id=profile.id, name="Version Control (Git)", estimated_hours=20.0)
    sk2 = Skill(profile_id=profile.id, name="C++ Programming", estimated_hours=40.0)
    phase = RoadmapPhase(
        roadmap_id="rm-3",
        phase_number=1,
        name="Phase 1",
        skills=[sk1, sk2],
        projects=[Project(name="Git Engine")],
    )
    rm = Roadmap(
        id="rm-3",
        profile_id=profile.id,
        title="Test Repro",
        objective="Master game development foundations",
        phases=[phase],
    )
    summaries = {
        "Version Control": SkillEvidenceSummary(skill_name="Version Control", evidence_count=3, weighted_score=0.85),
        "C++": SkillEvidenceSummary(skill_name="C++", evidence_count=7, weighted_score=0.95),
    }

    first = QualityScorer.calculate_score(rm, profile, summaries)
    second = QualityScorer.calculate_score(rm, profile, summaries)
    assert first.overall_score == second.overall_score
    assert first.market_alignment == second.market_alignment
    assert first.evidence_strength == second.evidence_strength


def test_skill_graph_independent_parallel_skills() -> None:
    from roadmap.application.graph.builder import SkillGraphBuilder
    from roadmap.domain.entities.skill import SkillDependency, SkillNode

    # C++ and Git & Version Control are parallel foundations (neither requires the other)
    nodes = [
        SkillNode(name="C++", category="programming", estimated_hours=40.0),
        SkillNode(name="Git & Version Control", category="tools", estimated_hours=15.0),
        SkillNode(name="Linear Algebra", category="math", estimated_hours=30.0),
    ]
    deps = [
        SkillDependency(prerequisite_skill="C++", dependent_skill="Linear Algebra"),
    ]

    _, _, graph_val = SkillGraphBuilder.build(nodes, deps)
    assert graph_val.is_valid
    assert len(graph_val.cycles) == 0
    # Both C++ and Git & Version Control can start concurrently
    assert "C++" in graph_val.topological_order
    assert "Git & Version Control" in graph_val.topological_order
