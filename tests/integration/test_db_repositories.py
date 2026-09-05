"""Integration tests for SQLite repositories."""

from __future__ import annotations

import pytest

from roadmap.domain.entities.skill import Skill, SkillDependency
from roadmap.domain.entities.user_profile import UserProfile
from roadmap.domain.entities.progress_record import ProgressRecord
from roadmap.domain.value_objects import DependencyType, Priority, SkillLevel, SkillStatus
from roadmap.shared.ids import new_id
from roadmap.storage.repositories.profile_repository import SqliteProfileRepository
from roadmap.storage.repositories.skill_repository import SqliteSkillRepository
from roadmap.storage.repositories.progress_repository import SqliteProgressRepository


def make_profile() -> UserProfile:
    return UserProfile(
        id=new_id(), name="Alice",
        target_goal="Become a Game Programmer",
        target_role="Gameplay Programmer",
        current_level=SkillLevel.FAMILIAR,
        current_skills=["C++", "Git"],
        programming_languages=["C++", "Lua"],
        study_hours_per_day=2.0,
        deadline_months=12,
    )


class TestProfileRepository:
    def test_save_and_load(self, db_session) -> None:
        repo = SqliteProfileRepository(db_session)
        profile = make_profile()
        repo.save(profile)
        db_session.flush()

        loaded = repo.load()
        assert loaded is not None
        assert loaded.id == profile.id
        assert loaded.name == "Alice"
        assert loaded.current_skills == ["C++", "Git"]
        assert loaded.programming_languages == ["C++", "Lua"]

    def test_exists_returns_true_after_save(self, db_session) -> None:
        repo = SqliteProfileRepository(db_session)
        assert not repo.exists()
        repo.save(make_profile())
        db_session.flush()
        assert repo.exists()

    def test_update_profile(self, db_session) -> None:
        repo = SqliteProfileRepository(db_session)
        profile = make_profile()
        repo.save(profile)
        db_session.flush()

        profile.name = "Bob"
        profile.study_hours_per_day = 4.0
        profile.touch()
        repo.save(profile)
        db_session.flush()

        loaded = repo.load()
        assert loaded.name == "Bob"
        assert loaded.study_hours_per_day == 4.0

    def test_delete_removes_profile(self, db_session) -> None:
        repo = SqliteProfileRepository(db_session)
        repo.save(make_profile())
        db_session.flush()
        assert repo.exists()
        repo.delete()
        db_session.flush()
        assert not repo.exists()

    def test_skill_level_enum_roundtrip(self, db_session) -> None:
        repo = SqliteProfileRepository(db_session)
        profile = make_profile()
        profile.current_level = SkillLevel.PROFICIENT
        repo.save(profile)
        db_session.flush()
        loaded = repo.load()
        assert loaded.current_level == SkillLevel.PROFICIENT


class TestSkillRepository:
    def test_save_and_load_skill(self, db_session) -> None:
        # Need a profile first (FK constraint)
        profile = make_profile()
        SqliteProfileRepository(db_session).save(profile)
        db_session.flush()

        repo = SqliteSkillRepository(db_session)
        skill = Skill(
            id=new_id(), profile_id=profile.id, name="C++",
            category="programming",
            current_level=SkillLevel.FAMILIAR,
            target_level=SkillLevel.PROFICIENT,
            priority=Priority.HIGH,
            estimated_hours=120.0,
        )
        repo.save_skill(skill)
        db_session.flush()

        skills = repo.load_skills(profile.id)
        assert len(skills) == 1
        assert skills[0].name == "C++"
        assert skills[0].priority == Priority.HIGH
        assert skills[0].estimated_hours == 120.0

    def test_save_dependency(self, db_session) -> None:
        profile = make_profile()
        SqliteProfileRepository(db_session).save(profile)
        db_session.flush()

        repo = SqliteSkillRepository(db_session)
        cpp = Skill(id=new_id(), profile_id=profile.id, name="C++")
        oop = Skill(id=new_id(), profile_id=profile.id, name="OOP")
        repo.save_skills([cpp, oop])
        db_session.flush()

        dep = SkillDependency(
            id=new_id(), from_skill_id=cpp.id, to_skill_id=oop.id,
            dependency_type=DependencyType.REQUIRES,
        )
        repo.save_dependency(dep)
        db_session.flush()

        deps = repo.load_dependencies(profile.id)
        assert len(deps) == 1
        assert deps[0].from_skill_id == cpp.id
        assert deps[0].to_skill_id == oop.id


class TestProgressRepository:
    def test_save_and_load_progress(self, db_session) -> None:
        profile = make_profile()
        SqliteProfileRepository(db_session).save(profile)
        db_session.flush()

        repo = SqliteProgressRepository(db_session)
        skill_id = new_id()
        record = ProgressRecord(
            id=new_id(), profile_id=profile.id,
            skill_id=skill_id, skill_name="C++",
            completion_percentage=75.0,
            notes="Getting there",
        )
        repo.save(record)
        db_session.flush()

        loaded = repo.load_for_skill(profile.id, skill_id)
        assert loaded is not None
        assert loaded.completion_percentage == 75.0
        assert loaded.skill_name == "C++"

    def test_load_all_returns_all_records(self, db_session) -> None:
        profile = make_profile()
        SqliteProfileRepository(db_session).save(profile)
        db_session.flush()

        repo = SqliteProgressRepository(db_session)
        for i in range(3):
            record = ProgressRecord(
                id=new_id(), profile_id=profile.id,
                skill_id=new_id(), skill_name=f"Skill{i}",
                completion_percentage=float(i * 25),
            )
            repo.save(record)
        db_session.flush()

        all_records = repo.load_all(profile.id)
        assert len(all_records) == 3
