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
    llm_provider: str = Field(
        default="openai",
        validation_alias=AliasChoices("ROADMAP_LLM_PROVIDER", "LLM_PROVIDER"),
        description="LLM provider name (openai | fake | mock)",
    )
    llm_model: str = Field(
        default="gpt-4o",
        validation_alias=AliasChoices("OPENAI_MODEL", "ROADMAP_LLM_MODEL", "LLM_MODEL"),
        description="LLM model identifier",
    )
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4096, gt=0)
    llm_max_retries: int = Field(default=3, ge=1, le=10)

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

    # ── Research Limits & Concurrency ──────────────────────────────────────
    research_concurrency: int = Field(default=5, ge=1, le=20)
    agent_max_revisions: int = Field(default=3, ge=1, le=10)
    research_timeout_seconds: int = Field(default=120, ge=10)

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
