"""
Application settings loaded from environment variables.

All settings have sensible defaults for local development.
Production deployments must provide explicit values via environment.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration object.  All values can be overridden via
    environment variables or a .env file located in the working directory.
    """

    model_config = SettingsConfigDict(
        env_prefix="ROADMAP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    env: str = Field(default="development", description="Runtime environment")
    log_level: str = Field(default="INFO", description="Logging level")
    data_dir: Path = Field(
        default=Path.home() / ".roadmap",
        description="Directory for user data (DB, cache)",
    )

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = Field(
        default="",  # computed below if empty
        description="SQLAlchemy database URL",
    )

    # ── LLM Provider ─────────────────────────────────────────────────────
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "ROADMAP_OPENAI_API_KEY"),
        description="OpenAI API key (from OPENAI_API_KEY or ROADMAP_OPENAI_API_KEY)",
    )
    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "ROADMAP_GEMINI_API_KEY"),
        description="Google Gemini API key (from GEMINI_API_KEY or ROADMAP_GEMINI_API_KEY)",
    )
    openai_model: str = Field(
        default="gpt-4o",
        validation_alias=AliasChoices("OPENAI_MODEL", "ROADMAP_OPENAI_MODEL"),
        description="OpenAI model identifier",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("GEMINI_MODEL", "ROADMAP_GEMINI_MODEL"),
        description="Gemini model identifier",
    )
    llm_provider: str = Field(
        default="gemini",
        validation_alias=AliasChoices("ROADMAP_LLM_PROVIDER", "LLM_PROVIDER"),
        description="LLM provider name (gemini | openai | fake | mock)",
    )
    llm_model: str = Field(
        default="",
        validation_alias=AliasChoices("ROADMAP_LLM_MODEL", "LLM_MODEL"),
        description="Universal LLM model override (takes precedence over provider-specific models)",
    )
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4096, gt=0)
    llm_max_retries: int = Field(default=3, ge=1, le=10)

    # ── Rate Limiting & Budgets ───────────────────────────────────────────
    llm_requests_per_minute: float = Field(
        default=4.0,
        ge=0.5,
        le=60.0,
        validation_alias=AliasChoices("ROADMAP_LLM_REQUESTS_PER_MINUTE", "LLM_REQUESTS_PER_MINUTE"),
        description="Client-side rate limit (requests per minute)",
    )
    daily_llm_budget: int = Field(
        default=15,
        ge=1,
        validation_alias=AliasChoices("ROADMAP_DAILY_LLM_BUDGET", "DAILY_LLM_BUDGET"),
        description="Global daily application request budget",
    )
    research_llm_budget: int = Field(
        default=5,
        ge=1,
        validation_alias=AliasChoices("ROADMAP_RESEARCH_LLM_BUDGET", "RESEARCH_LLM_BUDGET"),
        description="Daily request budget for research workflow",
    )
    generation_llm_budget: int = Field(
        default=5,
        ge=1,
        validation_alias=AliasChoices("ROADMAP_GENERATION_LLM_BUDGET", "GENERATION_LLM_BUDGET"),
        description="Daily request budget for generation workflow",
    )
    evaluation_llm_budget: int = Field(
        default=5,
        ge=1,
        validation_alias=AliasChoices("ROADMAP_EVALUATION_LLM_BUDGET", "EVALUATION_LLM_BUDGET"),
        description="Daily request budget for evaluation/revision workflow",
    )
    llm_budget_window_hours: int = Field(
        default=24,
        ge=1,
        validation_alias=AliasChoices("ROADMAP_LLM_BUDGET_WINDOW_HOURS", "LLM_BUDGET_WINDOW_HOURS"),
        description="Sliding window duration in hours for application budget accounting",
    )
    llm_provider_cooldown_seconds: int = Field(
        default=3600,
        ge=60,
        validation_alias=AliasChoices("ROADMAP_LLM_PROVIDER_COOLDOWN_SECONDS", "LLM_PROVIDER_COOLDOWN_SECONDS"),
        description="Cooldown duration when provider daily quota is exhausted and reset time is unknown",
    )

    # ── Search Provider ───────────────────────────────────────────────────
    exa_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("EXA_API_KEY", "ROADMAP_EXA_API_KEY"),
        description="Exa search API key (from EXA_API_KEY or ROADMAP_EXA_API_KEY)",
    )
    search_provider: str = Field(
        default="mock",
        validation_alias=AliasChoices("ROADMAP_SEARCH_PROVIDER", "SEARCH_PROVIDER"),
        description="Search provider name (exa | mock | fake)",
    )
    search_max_results: int = Field(default=10, ge=1, le=50)

    # ── Research Cache ────────────────────────────────────────────────────
    cache_ttl_hours: int = Field(default=24, ge=1)
    cache_max_size_mb: int = Field(default=512, ge=64)

    # ── Research Limits & Batching ─────────────────────────────────────────
    research_concurrency: int = Field(default=5, ge=1, le=20)
    agent_max_revisions: int = Field(default=3, ge=1, le=10)
    research_timeout_seconds: int = Field(default=120, ge=10)
    research_max_sources: int = Field(
        default=15,
        ge=1,
        le=50,
        validation_alias=AliasChoices("ROADMAP_RESEARCH_MAX_SOURCES", "RESEARCH_MAX_SOURCES"),
        description="Maximum number of high-value sources to deeply analyze with LLM",
    )
    research_batch_size: int = Field(
        default=5,
        ge=1,
        le=15,
        validation_alias=AliasChoices("ROADMAP_RESEARCH_BATCH_SIZE", "RESEARCH_BATCH_SIZE"),
        description="Number of web pages to batch in a single LLM extraction request",
    )
    research_max_content_chars: int = Field(
        default=3500,
        ge=500,
        le=20000,
        validation_alias=AliasChoices("ROADMAP_RESEARCH_MAX_CONTENT_CHARS", "RESEARCH_MAX_CONTENT_CHARS"),
        description="Maximum character budget per page during batch extraction",
    )

    @field_validator("data_dir", mode="before")
    @classmethod
    def expand_data_dir(cls, v: object) -> Path:
        return Path(str(v)).expanduser().resolve()

    @property
    def resolved_database_url(self) -> str:
        """Return a fully-resolved database URL, expanding ~ in SQLite paths."""
        if self.database_url:
            if self.database_url.startswith("sqlite:///~"):
                return self.database_url.replace(
                    "sqlite:///~", f"sqlite:///{Path.home()}", 1
                )
            return self.database_url
        # Default: SQLite in data_dir
        db_path = self.data_dir / "roadmap.db"
        return f"sqlite:///{db_path}"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    def ensure_data_dir(self) -> None:
        """Create data and cache directories if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


# Singleton — import this from anywhere
settings = Settings()
