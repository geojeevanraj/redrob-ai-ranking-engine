"""Centralized, environment-driven configuration.

Settings are loaded from environment variables (and an optional `.env` file)
and cached so the rest of the app depends on a single, validated source of
truth. Supports `development`, `testing`, and `production` via `APP_ENV`.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Field names map to UPPER_CASE environment variables (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Core ────────────────────────────────────────────────
    app_name: str = "AI Recruitment Intelligence Platform"
    app_version: str = "0.1.0"
    app_env: Environment = Field(default=Environment.DEVELOPMENT)

    # ── Server ──────────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # ── CORS ────────────────────────────────────────────────
    backend_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ── Logging ─────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = False

    # ── Database ────────────────────────────────────────────
    postgres_user: str = "recruit"
    postgres_password: str = "recruit_dev_pw"
    postgres_db: str = "recruitment"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str | None = None

    # ── Document upload / storage ───────────────────────────
    document_storage_dir: str = "./var/uploads"
    max_upload_size_mb: int = 10
    allowed_document_extensions: str = "pdf,docx,txt"

    # ── Hidden Skill Inference ──────────────────────────────
    hidden_skill_min_confidence: float = 0.5
    hidden_skill_max_depth: int = 2
    hidden_skill_decay: float = 0.6
    hidden_skill_min_sources: int = 2
    hidden_skill_strong_single_threshold: float = 0.55

    # ── Candidate DNA ───────────────────────────────────────
    dna_top_threshold: float = 0.6
    dna_emerging_threshold: float = 0.3
    dna_confidence_items: int = 5
    dna_default_saturation: float = 3.0

    # ── Offline Ranking (Sprint 9.1) ────────────────────────
    ranking_dataset_path: str | None = None
    ranking_export_dir: str = "./var/rankings"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        """Async SQLAlchemy DSN, derived from parts unless overridden."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        return self.app_env is Environment.PRODUCTION

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_document_extensions.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single source of truth)."""
    return Settings()
