"""Tests for app.core.config — Settings loading and get_settings caching."""

import pytest

from app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Clear the lru_cache before and after every test in this module."""
    get_settings.cache_clear()
    yield  # type: ignore[misc]
    get_settings.cache_clear()


def test_settings_loads_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE_URL from environment is reflected in Settings."""
    url = "postgresql+asyncpg://user:pass@db:5432/mydb"
    monkeypatch.setenv("DATABASE_URL", url)
    settings = get_settings()
    assert settings.DATABASE_URL == url


def test_settings_default_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_LEVEL defaults to INFO when not set in environment."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    settings = get_settings()
    assert settings.LOG_LEVEL == "INFO"


def test_settings_custom_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """LOG_LEVEL env var overrides the default."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = get_settings()
    assert settings.LOG_LEVEL == "DEBUG"


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() returns the same instance on repeated calls."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_ignores_extra_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Extra env vars do not cause a validation error (extra='ignore')."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("UNKNOWN_VAR", "irrelevant")
    settings = get_settings()
    assert settings.DATABASE_URL is not None


def test_settings_instance_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings() returns a Settings instance."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    assert isinstance(get_settings(), Settings)
