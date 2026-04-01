# F-02: Backend Project Scaffold — Implementation Plan

**Owner:** backend-tdd-api-dev  
**Date:** 2026-03-30  
**Status:** In Progress

---

## Approach

TDD scaffold: write tests first for each module, then implement until green. 100% line + branch coverage gate enforced via `--cov-fail-under=100`.

All modules are kept minimal — only what the scaffold needs. Complexity is deferred to the feature tasks (F-05 through F-13) that own each concern.

---

## Key Decisions

1. **Lazy DB initialization** — `database.py` defines `init_db(url)` called from the FastAPI lifespan, not at import time. Avoids needing `DATABASE_URL` during test collection.

2. **`@lru_cache` on `get_settings()`** — single settings instance; tests call `get_settings.cache_clear()` to isolate.

3. **JSON logging in lifespan** — `configure_logging()` called in lifespan, not at module level, so pytest's log capture is not disturbed. Mocked in integration tests; tested in isolation.

4. **Tests in `backend/tests/`** — outside the `app/` package so they don't inflate coverage metrics. `--cov=app` only counts `app/`.

5. **`asyncio_mode = "auto"`** — no `@pytest.mark.asyncio` decorator needed on async test functions.

---

## File Structure

```
backend/
├── pyproject.toml              # Poetry + Ruff + mypy + pytest config
├── alembic.ini                 # Alembic config (url overridden in env.py)
├── alembic/
│   ├── env.py                  # Async migration runner
│   ├── script.py.mako          # Migration file template
│   └── versions/               # Empty; F-05 adds initial migration
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifespan, health endpoint
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Pydantic Settings + get_settings()
│   │   └── database.py         # Base, init_db, get_db dependency
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       └── __init__.py     # Empty APIRouter (populated by F-12/F-13)
│   ├── models/__init__.py
│   ├── schemas/__init__.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── parser/__init__.py
│   └── repositories/__init__.py
└── tests/
    ├── __init__.py
    ├── conftest.py             # Shared fixtures; sets DATABASE_URL before imports
    ├── unit/
    │   ├── __init__.py
    │   ├── test_health.py      # Health endpoint + logging coverage
    │   ├── test_config.py      # Settings loading coverage
    │   └── test_database.py   # init_db, get_db coverage
    └── integration/
        └── __init__.py
```

---

## Coverage Strategy

| Module | How Covered |
|---|---|
| `app/__init__.py` | Covered on import |
| `app/main.py` | `test_health.py` — TestClient with lifespan (mocked init_db); explicit formatter tests |
| `app/core/config.py` | `test_config.py` — monkeypatch env vars, cache clear |
| `app/core/database.py` | `test_database.py` — init_db with mock engine; get_db happy path + uninitialized path |
| `app/api/v1/__init__.py` | Covered on import (module-level `APIRouter()`) |
| All empty `__init__.py` | Covered on import (0 executable lines) |

---

## Validation Commands

```bash
cd /Users/devendran/Development/workspace/options-tracker/backend
poetry install
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy app
poetry run pytest --cov=app --cov-fail-under=100 --cov-branch -v
```
