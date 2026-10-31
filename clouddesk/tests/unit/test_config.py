"""Settings behaviour: offline defaults, secret handling, and the production guard."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import DEFAULT_JWT_SECRET, Settings, get_settings

# Every test builds Settings with `_env_file=None` so a developer's real .env
# can never change the outcome.


def make_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


class TestOfflineDefaults:
    """F14: the defaults must run with no API key, no Redis and no Docker."""

    def test_defaults_select_fake_providers(self) -> None:
        settings = make_settings()

        assert settings.demo_mode is True
        assert settings.llm_provider == "fake"
        assert settings.vector_store == "memory"
        assert settings.embedding_provider == "fake"
        assert settings.llm_api_key is None

    def test_defaults_need_no_redis(self) -> None:
        assert make_settings().use_in_memory_redis is True

    def test_real_redis_url_disables_the_fake(self) -> None:
        settings = make_settings(redis_url="redis://redis:6379/0")
        assert settings.use_in_memory_redis is False

    def test_use_fake_redis_overrides_a_configured_url(self) -> None:
        settings = make_settings(redis_url="redis://redis:6379/0", use_fake_redis=True)
        assert settings.use_in_memory_redis is True

    def test_embedding_dimensions_match_fake_embeddings(self) -> None:
        assert make_settings().embedding_dimensions == 384

    def test_sqlite_by_default(self) -> None:
        assert make_settings().database_url.startswith("sqlite+aiosqlite")


class TestApprovalPolicy:
    """F9: refunds are gated by default and the threshold is exact money."""

    def test_refunds_require_approval_by_default(self) -> None:
        assert make_settings().approval_required_for_refunds is True

    def test_zero_refund_threshold_by_default(self) -> None:
        assert make_settings().max_refund_without_approval == Decimal("0")

    def test_threshold_is_decimal_not_float(self) -> None:
        settings = make_settings(max_refund_without_approval="10.10")
        # The float trap: 10.10 is not representable, Decimal("10.10") is.
        assert settings.max_refund_without_approval == Decimal("10.10")
        assert isinstance(settings.max_refund_without_approval, Decimal)


class TestJwtSecret:
    """N1: Supabase wins when configured, and secrets never render in the clear."""

    def test_falls_back_to_jwt_secret(self) -> None:
        settings = make_settings(jwt_secret=SecretStr("local-secret"))
        assert settings.effective_jwt_secret == "local-secret"

    def test_supabase_secret_takes_precedence(self) -> None:
        settings = make_settings(
            jwt_secret=SecretStr("local-secret"),
            supabase_jwt_secret=SecretStr("supabase-secret"),
        )
        assert settings.effective_jwt_secret == "supabase-secret"

    @pytest.mark.parametrize("field", ["jwt_secret", "llm_api_key", "qdrant_api_key"])
    def test_secrets_are_masked_in_repr(self, field: str) -> None:
        settings = make_settings(**{field: SecretStr("super-secret-value")})

        assert "super-secret-value" not in repr(settings)
        assert "super-secret-value" not in str(settings)
        assert "super-secret-value" not in str(settings.model_dump())


class TestProductionGuard:
    """Refusing to boot is cheaper than serving traffic on the shipped secret."""

    def test_production_rejects_the_default_secret(self) -> None:
        with pytest.raises(ValidationError, match="still the development default"):
            make_settings(environment="production", demo_mode=False)

    def test_production_rejects_demo_mode(self) -> None:
        with pytest.raises(ValidationError, match="DEMO_MODE must be false"):
            make_settings(
                environment="production",
                demo_mode=True,
                jwt_secret=SecretStr("a-real-secret"),
            )

    def test_production_accepts_a_real_secret(self) -> None:
        settings = make_settings(
            environment="production",
            demo_mode=False,
            jwt_secret=SecretStr("a-real-secret"),
        )
        assert settings.is_production is True

    def test_supabase_secret_satisfies_the_guard(self) -> None:
        settings = make_settings(
            environment="production",
            demo_mode=False,
            supabase_jwt_secret=SecretStr("a-real-supabase-secret"),
        )
        assert settings.effective_jwt_secret != DEFAULT_JWT_SECRET

    def test_development_tolerates_the_default_secret(self) -> None:
        assert make_settings().effective_jwt_secret == DEFAULT_JWT_SECRET


class TestDerivedValues:
    def test_cors_origins_split_on_commas(self) -> None:
        settings = make_settings(cors_origins="http://a.test, http://b.test")
        assert settings.cors_origin_list == ["http://a.test", "http://b.test"]

    def test_cors_origins_drops_blanks(self) -> None:
        settings = make_settings(cors_origins="http://a.test,,  ,http://b.test")
        assert settings.cors_origin_list == ["http://a.test", "http://b.test"]

    def test_log_level_is_debug_in_demo(self) -> None:
        assert make_settings().log_level == "DEBUG"

    def test_log_level_is_info_in_production(self) -> None:
        settings = make_settings(
            environment="production", demo_mode=False, jwt_secret=SecretStr("x")
        )
        assert settings.log_level == "INFO"

    @pytest.mark.parametrize("value", ["production", "PROD", " Production "])
    def test_is_production_is_case_and_space_insensitive(self, value: str) -> None:
        settings = make_settings(environment=value, demo_mode=False, jwt_secret=SecretStr("x"))
        assert settings.is_production is True


class TestEnvironmentLoading:
    def test_reads_from_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "7")

        settings = make_settings()

        assert settings.llm_provider == "anthropic"
        assert settings.rate_limit_per_minute == 7

    def test_env_names_are_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("demo_mode", "false")
        assert make_settings().demo_mode is False

    def test_unknown_variables_are_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SOMETHING_UNRELATED", "value")
        make_settings()  # must not raise

    def test_rejects_an_unknown_vector_store(self) -> None:
        with pytest.raises(ValidationError):
            make_settings(vector_store="pinecone")


class TestCaching:
    def test_get_settings_is_cached(self) -> None:
        get_settings.cache_clear()
        assert get_settings() is get_settings()

    def test_cache_clear_rereads_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        get_settings.cache_clear()
        first = get_settings()

        monkeypatch.setenv("LLM_MODEL", "changed-after-first-read")
        assert get_settings() is first, "a .env change must not take effect without a restart"

        get_settings.cache_clear()
        assert get_settings().llm_model == "changed-after-first-read"

        get_settings.cache_clear()
