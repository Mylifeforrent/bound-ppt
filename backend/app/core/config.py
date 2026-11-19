from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Server configuration. Values come from the repository-root .env.

    M1 topology is a single API process with an in-process asyncio job runner.
    SQLite is the zero-setup local default; production MUST provide PostgreSQL.
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_base_url: str = "http://127.0.0.1:5173"
    session_secret: str = "dev-only-session-secret-change-me"
    auto_create_tables: bool = True
    serve_frontend: bool = True

    database_url: str = "sqlite+aiosqlite:///./backend/bound_ppt.db"
    direct_database_url: str = ""

    storage_backend: str = "local"
    storage_local_root: str = "./backend/storage"
    s3_endpoint: str = ""
    s3_region: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    model_provider: str = "stub"
    model_base_url: str = "https://api.openai.com/v1"
    model_api_key: str = ""
    model_id: str = "gpt-4o-mini"
    model_economy_id: str = ""
    model_quality_id: str = ""
    model_timeout_s: float = 90.0

    search_provider: str = "stub"
    search_api_key: str = ""
    search_cap_per_project: int = 12

    pilot_email: str = "pilot@boundppt.local"
    pilot_password: str = "boundppt-demo"
    pilot_name: str = "Pilot User"

    material_max_count: int = 6
    page_max_count: int = 30
    upload_max_bytes: int = 20 * 1024 * 1024
    ingest_max_chars: int = 120_000

    page_history_max_depth: int = 20
    job_max_attempts: int = 3
    generation_workers: int = 4
    ingestion_workers: int = 2
    export_workers: int = 1
    job_lease_seconds: int = 120
    job_deadline_seconds: int = 900
    export_timeout_seconds: int = 300

    question_catalog_version: str = "2026-11-01"
    style_catalog_version: str = "1"

    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str = ""
    sentry_dsn: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def storage_root(self) -> Path:
        path = Path(self.storage_local_root)
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()

    @model_validator(mode="after")
    def _guard_mock_on_paid_path(self) -> Settings:
        if self.is_production:
            if self.model_provider == "stub":
                raise ValueError("MODEL_PROVIDER=stub is forbidden when APP_ENV=production (FR-7.18)")
            if self.search_provider == "stub":
                raise ValueError("SEARCH_PROVIDER=stub is forbidden when APP_ENV=production (FR-2.20)")
            if self.is_sqlite:
                raise ValueError("SQLite is a local development default; production requires PostgreSQL")
            if self.auto_create_tables:
                raise ValueError("AUTO_CREATE_TABLES must be false in production; run `alembic upgrade head`")
        return self

    @property
    def economy_model(self) -> str:
        return self.model_economy_id or self.model_id

    @property
    def quality_model(self) -> str:
        return self.model_quality_id or self.model_id


@lru_cache
def get_settings() -> Settings:
    return Settings()
