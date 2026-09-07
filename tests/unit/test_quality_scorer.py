"""Unit tests for QualityScorer."""

from __future__ import annotations

from roadmap.domain.entities.evidence_aggregation import SkillEvidenceSummary
from roadmap.domain.entities.learning_resource import Project
from roadmap.domain.entities.roadmap import Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.services.quality_scorer import QualityScorer
from roadmap.domain.value_objects import Priority


def test_quality_scorer_baseline() -> None:
    profile = UserProfile(
        name="Test",
        target_goal="Become a Game Developer",
        target_role="Gameplay Programmer",
        study_hours_per_day=3.0,
        deadline_months=6,
    )

    sk1 = Skill(profile_id=profile.id, name="C++", estimated_hours=40.0, priority=Priority.CRITICAL)
    sk2 = Skill(profile_id=profile.id, name="Math", estimated_hours=30.0, priority=Priority.HIGH, prerequisite_names=["C++"])

    proj = Project(name="Custom Engine", required_skill_names=["C++", "Math"])

    phase = RoadmapPhase(
        roadmap_id="rm1",
        phase_number=1,
        name="Phase 1",
        objective="Master systems programming foundations",
        skills=[sk1, sk2],
        projects=[proj],
        estimated_weeks=6.0,
    )

    roadmap = Roadmap(
        id="rm1",
        profile_id=profile.id,
        title="Game Dev Roadmap",
        objective="Become job-ready gameplay programmer",
        phases=[phase],
        total_weeks=6,
    )

    ev_summaries = {
        "C++": SkillEvidenceSummary(skill_name="C++", evidence_count=3, unique_source_count=2, weighted_score=0.90),
        "Math": SkillEvidenceSummary(skill_name="Math", evidence_count=2, unique_source_count=2, weighted_score=0.85),
    }

    score = QualityScorer.calculate_score(
        roadmap=roadmap,
        profile=profile,
        evidence_summaries=ev_summaries,
        has_cycles=False,
    )

    assert score.overall_score >= 80.0
    assert score.goal_alignment >= 80.0
    assert score.market_alignment >= 80.0
    assert score.dependency_correctness == 100.0
    assert score.portfolio_value == 90.0


def test_quality_scorer_cycle_penalty() -> None:
    profile = UserProfile(
        name="Test",
        target_goal="Become a Game Developer",
        study_hours_per_day=1.0,
        deadline_months=1,
    )
    roadmap = Roadmap(
        id="rm1",
        profile_id=profile.id,
        title="Test Roadmap",
        objective="",
        phases=[],
    )

    score = QualityScorer.calculate_score(
        roadmap=roadmap,
        profile=profile,
        has_cycles=True,
    )

    assert score.dependency_correctness == 0.0
    assert any("Dependency cycles detected" in n for n in score.scoring_notes)


def test_quality_scorer_normalized_evidence_matching() -> None:
    profile = UserProfile(
        name="Test",
        target_goal="Become a Game Developer",
        target_role="Gameplay Programmer",
        study_hours_per_day=3.0,
        deadline_months=6,
    )

    # Descriptive skill names typical of LLM output
    sk1 = Skill(profile_id=profile.id, name="C++ Programming", estimated_hours=40.0, priority=Priority.CRITICAL)
    sk2 = Skill(profile_id=profile.id, name="Version Control (Git)", estimated_hours=20.0, priority=Priority.HIGH)

    phase = RoadmapPhase(
        roadmap_id="rm1",
        phase_number=1,
        name="Phase 1",
        objective="Master foundations",
        skills=[sk1, sk2],
        projects=[Project(name="Test Project")],
        estimated_weeks=4.0,
    )

    roadmap = Roadmap(
        id="rm1",
        profile_id=profile.id,
        title="Game Dev Roadmap",
        objective="Become gameplay programmer",
        phases=[phase],
        total_weeks=4,
    )

    # Canonical evidence keys
    ev_summaries = {
        "C++": SkillEvidenceSummary(skill_name="C++", evidence_count=5, unique_source_count=3, weighted_score=0.92),
        "Version Control": SkillEvidenceSummary(skill_name="Version Control", evidence_count=2, unique_source_count=1, weighted_score=0.80),
    }

    score = QualityScorer.calculate_score(
        roadmap=roadmap,
        profile=profile,
        evidence_summaries=ev_summaries,
    )

    # Should match both skills via normalization and achieve full evidence grounding
    assert score.evidence_strength == 100.0
    assert score.market_alignment > 80.0
    assert score.overall_score >= 85.0
