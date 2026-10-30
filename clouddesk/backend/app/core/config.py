"""Application settings.

Every value comes from the environment or a git-ignored `.env`. The full list of
variables is CLAUDE.md §10.1; `.env.example` must stay in step with this module.

Two rules this file exists to enforce:

1. **Offline by default.** The defaults select the fake LLM provider, the in-memory
   vector store and SQLite, so `make test` runs with no API key and no Docker
   (CLAUDE.md F14).
2. **Secrets stay secret.** Every credential is a `SecretStr`, so it renders as
   `**********` in logs, tracebacks and `repr()` rather than leaking (CLAUDE.md §9).

`get_settings()` is `lru_cache`d, so the process must be restarted after a `.env`
change.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Refusing to start with this in production is cheaper than discovering it later.
DEFAULT_JWT_SECRET = "dev-only-insecure-change-me"


class Settings(BaseSettings):
    """Runtime configuration, read once per process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime -----------------------------------------------------------
    demo_mode: bool = True
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"

    # --- Auth (N1) ---------------------------------------------------------
    jwt_secret: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    # Set this to the Supabase JWT secret to accept Supabase-issued tokens unchanged.
    supabase_jwt_secret: SecretStr | None = None

    # --- Persistence -------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./data/support.db"
    checkpoint_db_path: str = "./data/checkpoints.db"

    # --- Cache and short-term memory ---------------------------------------
    # An empty REDIS_URL means "no Redis available", which falls back to fakeredis.
    redis_url: str = ""
    use_fake_redis: bool = False

    # --- LLM ---------------------------------------------------------------
    llm_provider: str = "fake"
    llm_api_key: SecretStr | None = None
    llm_model: str = "fake"

    # --- Embeddings and vector store ---------------------------------------
    embedding_provider: str = "fake"
    embedding_model: str = "fake"
    # 384 matches FakeEmbeddings; changing it requires POST /knowledge/reindex.
    embedding_dimensions: int = 384
    vector_store: Literal["memory", "qdrant"] = "memory"
    qdrant_url: str = ""
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "clouddesk_knowledge"

    # --- Approval policy (F9) ----------------------------------------------
    approval_required_for_refunds: bool = True
    # Decimal, not float: this is money and it is compared against refund amounts.
    max_refund_without_approval: Decimal = Decimal("0")

    # --- Limits ------------------------------------------------------------
    tool_timeout_seconds: float = 30.0
    rate_limit_per_minute: int = 120
    sample_data_dir: str = "sample_data"

    # --- Tracing (optional) -------------------------------------------------
    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr | None = None
    langchain_project: str = "clouddesk-support"

    # --- Derived values -----------------------------------------------------

    @property
    def effective_jwt_secret(self) -> str:
        """The secret tokens are actually verified against.

        Supabase wins when configured, so tokens minted by Supabase validate
        without a second code path.
        """
        if self.supabase_jwt_secret is not None:
            return self.supabase_jwt_secret.get_secret_value()
        return self.jwt_secret.get_secret_value()

    @property
    def cors_origin_list(self) -> list[str]:
        """`CORS_ORIGINS` as a list. Comma-separated, blanks dropped."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def use_in_memory_redis(self) -> bool:
        """True when fakeredis should stand in for a real Redis."""
        return self.use_fake_redis or not self.redis_url

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"prod", "production"}

    @property
    def log_level(self) -> str:
        """Derived rather than configured, so there is no undocumented env var."""
        return "INFO" if self.is_production or not self.demo_mode else "DEBUG"

    # --- Guards --------------------------------------------------------------

    @model_validator(mode="after")
    def _reject_insecure_production(self) -> Settings:
        """Fail fast rather than serve production traffic on the shipped secret."""
        if self.is_production:
            if self.effective_jwt_secret == DEFAULT_JWT_SECRET:
                raise ValueError(
                    "JWT_SECRET is still the development default. "
                    "Set JWT_SECRET or SUPABASE_JWT_SECRET before running in production."
                )
            if self.demo_mode:
                raise ValueError("DEMO_MODE must be false when ENVIRONMENT is production.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings.

    Cached: change `.env`, then restart the server (CLAUDE.md §10).
    """
    return Settings()
