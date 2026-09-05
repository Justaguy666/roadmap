"""Domain entities package — re-exports all entities."""

from roadmap.domain.entities.goal import Competency, Goal
from roadmap.domain.entities.learning_resource import LearningResource, Project
from roadmap.domain.entities.progress_record import ProgressRecord
from roadmap.domain.entities.roadmap import Milestone, Roadmap, RoadmapPhase
from roadmap.domain.entities.skill import Skill, SkillDependency
from roadmap.domain.entities.source import Evidence, Recommendation, Source
from roadmap.domain.entities.user_profile import UserProfile

__all__ = [
    "Competency",
    "Evidence",
    "Goal",
    "LearningResource",
    "Milestone",
    "ProgressRecord",
    "Project",
    "Recommendation",
    "Roadmap",
    "RoadmapPhase",
    "Skill",
    "SkillDependency",
    "Source",
    "UserProfile",
]
