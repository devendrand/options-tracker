"""
Shared pytest fixtures.

DATABASE_URL is set here at module level — before any app module is imported —
so that pydantic-settings can resolve it during test collection.
"""

import os

# Must precede all app imports so pydantic-settings resolves DATABASE_URL.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test_db",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    """Return a TestClient that does NOT trigger the app lifespan."""
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def clear_settings_cache() -> None:
    """Clear the lru_cache on get_settings before and after each test."""
    get_settings.cache_clear()
    yield  # type: ignore[misc]
    get_settings.cache_clear()
