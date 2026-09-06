"""
Domain value objects — SkillLevel, Priority, SkillStatus,
BudgetPreference, ResourceType, SourceType.

These are immutable enums used throughout the domain.
They have no dependencies on external libraries.
"""

from __future__ import annotations

from enum import Enum


class SkillLevel(str, Enum):
    """
    Proficiency level for a skill.

    Ordered from lowest to highest:
      MISSING < FAMILIAR < LEARNING < PROFICIENT < MASTERED
    """

    MISSING = "missing"
    FAMILIAR = "familiar"
    LEARNING = "learning"
    PROFICIENT = "proficient"
    MASTERED = "mastered"

    def numeric(self) -> int:
        """Return a numeric value for ordering (0 = missing, 4 = mastered)."""
        return {
            SkillLevel.MISSING: 0,
            SkillLevel.FAMILIAR: 1,
            SkillLevel.LEARNING: 2,
            SkillLevel.PROFICIENT: 3,
            SkillLevel.MASTERED: 4,
        }[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SkillLevel):
            return NotImplemented
        return self.numeric() < other.numeric()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SkillLevel):
            return NotImplemented
        return self.numeric() <= other.numeric()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SkillLevel):
            return NotImplemented
        return self.numeric() > other.numeric()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SkillLevel):
            return NotImplemented
        return self.numeric() >= other.numeric()

    @property
    def label(self) -> str:
        return self.value.capitalize()

    @property
    def gap_from_mastered(self) -> int:
        """How many levels away from MASTERED."""
        return SkillLevel.MASTERED.numeric() - self.numeric()


class Priority(str, Enum):
    """Relative priority for a skill or recommendation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def numeric(self) -> int:
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.numeric() < other.numeric()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.numeric() <= other.numeric()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.numeric() > other.numeric()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.numeric() >= other.numeric()


class SkillStatus(str, Enum):
    """Lifecycle status of a skill in the roadmap."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    SKIPPED = "skipped"


class BudgetPreference(str, Enum):
    """User's willingness to pay for learning resources."""

    FREE = "free"          # Free resources only
    LOW = "low"            # Up to ~$50
    MEDIUM = "medium"      # Up to ~$200
    ANY = "any"            # No budget restriction


class ResourceType(str, Enum):
    """Category of a learning resource."""

    BOOK = "book"
    MOOC = "mooc"
    COURSE = "course"
    DOCS = "docs"
    GITHUB = "github"
    TUTORIAL = "tutorial"
    VIDEO = "video"
    LECTURE = "lecture"
    PAPER = "paper"
    PROJECT = "project"
    OTHER = "other"


class SourceType(str, Enum):
    """Category of an evidence source."""

    JOB_POSTING = "job_posting"
    COMPANY_CAREER_PAGE = "company_career_page"
    INDUSTRY_REPORT = "industry_report"
    UNIVERSITY_CURRICULUM = "university_curriculum"
    OFFICIAL_DOCUMENTATION = "official_documentation"
    OFFICIAL_DOCS = "official_docs"  # alias for backwards compatibility
    COURSE = "course"
    BOOK = "book"
    GITHUB = "github"
    TECHNICAL_ARTICLE = "technical_article"
    ARTICLE = "article"  # alias
    BLOG_POST = "blog_post"  # alias
    SURVEY = "survey"
    PAPER = "paper"
    UNIVERSITY = "university"  # alias
    OTHER = "other"


class DependencyType(str, Enum):
    """Type of prerequisite relationship between skills."""

    REQUIRES = "requires"       # Hard prerequisite — must be done first
    PREREQUISITE = "prerequisite"  # Alias for hard prerequisite
    ENHANCES = "enhances"       # Soft prerequisite — recommended first
    COMPLEMENTARY = "complementary"  # Complementary skill relationship
    SPECIALIZATION = "specialization"  # Advanced elective or niche specialization
    OPTIONAL = "optional"       # Nice to have before


class FailureCategory(str, Enum):
    """Standardized failure categories for LLM requests and budget accounting."""

    APPLICATION_BUDGET_EXCEEDED = "APPLICATION_BUDGET_EXCEEDED"
    PROVIDER_DAILY_QUOTA_EXCEEDED = "PROVIDER_DAILY_QUOTA_EXCEEDED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    TRANSIENT_PROVIDER_ERROR = "TRANSIENT_PROVIDER_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


class LLMWorkflow(str, Enum):
    """Workflows that consume LLM request budget."""

    RESEARCH = "research"
    GENERATION = "generation"
    EVALUATION = "evaluation"
    OTHER = "other"
