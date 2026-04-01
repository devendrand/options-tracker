"""Tests for app.core.database — init_db, get_db, and Base."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

import app.core.database as db_module
from app.core.database import Base, get_db, init_db

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


def test_base_is_declarative_base() -> None:
    """Base must be a DeclarativeBase subclass for ORM models."""
    assert issubclass(Base, DeclarativeBase)


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


def test_init_db_sets_engine_and_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_db populates module-level _engine and _session_factory."""
    monkeypatch.setattr(db_module, "_engine", None)
    monkeypatch.setattr(db_module, "_session_factory", None)

    with (
        patch("app.core.database.create_async_engine") as mock_engine,
        patch("app.core.database.async_sessionmaker") as mock_factory,
    ):
        init_db("postgresql+asyncpg://test:test@localhost:5432/test_db")

    mock_engine.assert_called_once_with(
        "postgresql+asyncpg://test:test@localhost:5432/test_db", echo=False
    )
    mock_factory.assert_called_once_with(
        mock_engine.return_value,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# get_db — uninitialized path
# ---------------------------------------------------------------------------


async def test_get_db_raises_when_not_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_db raises RuntimeError when init_db has not been called."""
    monkeypatch.setattr(db_module, "_session_factory", None)

    with pytest.raises(RuntimeError, match="Database not initialized"):
        async for _ in get_db():
            pass  # pragma: no cover


# ---------------------------------------------------------------------------
# get_db — happy path
# ---------------------------------------------------------------------------


async def test_get_db_yields_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_db yields an AsyncSession from the session factory."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_cm)

    monkeypatch.setattr(db_module, "_session_factory", mock_factory)

    collected: list[AsyncSession] = []
    async for session in get_db():
        collected.append(session)

    assert len(collected) == 1
    assert collected[0] is mock_session
    mock_factory.assert_called_once_with()
    mock_cm.__aenter__.assert_awaited_once()
    mock_cm.__aexit__.assert_awaited_once()
