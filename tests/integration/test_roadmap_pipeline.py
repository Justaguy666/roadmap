"""
Integration tests for the full mocked end-to-end roadmap pipeline.

Workflow under test:
  UserProfile saved to SQLite
      ↓
  Goal Analysis (FakeLLMProvider)
      ↓
  Skill Gap Analysis (Deterministic)
      ↓
  Roadmap Generation (FakeLLMProvider)
      ↓
  Validation (RoadmapValidator)
      ↓
  Persistence (SqliteRoadmapRepository, SqliteSkillRepository)
      ↓
  Verification from DB
"""

from __future__ import annotations

from roadmap.application.use_cases.generate_roadmap import GenerateRoadmapUseCase
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.value_objects.enums import SkillLevel
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.shared.ids import new_id
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.roadmap_repository import SqliteRoadmapRepository
from roadmap.storage.repositories.skill_repository import SqliteSkillRepository


class TestRoadmapPipelineIntegration:
    def test_end_to_end_mocked_generation_pipeline(self, db_session) -> None:
        # 1. Setup SQLite repositories
        profile_repo = SqliteProfileRepository(db_session)
        roadmap_repo = SqliteRoadmapRepository(db_session)
        skill_repo = SqliteSkillRepository(db_session)

        # 2. Persist user profile
        profile = UserProfile(
            id=new_id(),
            name="Diana",
            target_goal="Become a Game Programmer",
            target_role="Gameplay Programmer",
            current_level=SkillLevel.FAMILIAR,
            current_skills=["C++"],
            study_hours_per_day=2.5,
            deadline_months=12,
        )
        profile_repo.save(profile)
        db_session.flush()

        assert profile_repo.exists()

        # 3. Instantiate pipeline with FakeLLMProvider
        fake_llm = FakeLLMProvider()
        generate_uc = GenerateRoadmapUseCase(
            llm_provider=fake_llm,
            profile_repo=profile_repo,
            roadmap_repo=roadmap_repo,
            skill_repo=skill_repo,
            max_retries=3,
        )

        # 4. Execute pipeline
        roadmap, goal_analysis, skill_gaps, val_result = generate_uc.execute(profile)
        db_session.flush()

        # 5. Assertions on generated objects
        assert val_result.is_valid is True
        assert goal_analysis.target_role == "Gameplay Programmer"
        assert skill_gaps.total_gaps >= 1
        assert len(roadmap.phases) == 2
        assert roadmap.total_weeks == 14

        # 6. Verify persistence in SQLite database
        loaded_roadmap = roadmap_repo.load_latest(profile.id)
        assert loaded_roadmap is not None
        assert loaded_roadmap.id == roadmap.id
        assert loaded_roadmap.title == roadmap.title
        assert len(loaded_roadmap.phases) == 2

        # Check phase 1 skills loaded from DB
        p1 = loaded_roadmap.phases[0]
        assert len(p1.skills) == 2
        assert any(s.name == "C++" for s in p1.skills)
        assert len(p1.projects) == 1
        assert len(p1.milestones) == 1

        # Check phase 2 skills loaded from DB
        p2 = loaded_roadmap.phases[1]
        assert len(p2.skills) == 3
        assert any(s.name == "Linear Algebra" for s in p2.skills)

        # Check skill repository has persisted all skills
        persisted_skills = skill_repo.load_skills(profile.id)
        assert len(persisted_skills) == 5

        # Check dependencies persisted
        deps = skill_repo.load_dependencies(profile.id)
        assert len(deps) >= 1
