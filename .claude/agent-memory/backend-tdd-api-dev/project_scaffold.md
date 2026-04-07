---
name: Backend Scaffold Architecture Decisions
description: Key architecture decisions made during F-02 backend scaffold — lazy DB init, JSON logging, test layout
type: project
---

Lazy DB initialization via `init_db(url)` called from FastAPI lifespan, NOT at module import time.

**Why:** Allows test collection without DATABASE_URL env var set; avoids import-time side effects.

**How to apply:** Unit tests mock `init_db` via `patch("app.main.init_db")`; `tests/conftest.py` sets `DATABASE_URL` env var at module level (before any app imports) using `os.environ.setdefault`.

---

`get_settings()` uses `@lru_cache`; tests call `get_settings.cache_clear()` to isolate.

**Why:** Single settings instance is correct for prod; but tests must be able to override env vars independently.

**How to apply:** test_config.py has `autouse=True` fixture that calls `cache_clear()` before/after every test.

---

Structured JSON logging (`JSONFormatter`) configured in lifespan, NOT at module level.

**Why:** Calling `logging.basicConfig()` at module import time would interfere with pytest's log capture plugin.

**How to apply:** `configure_logging()` is mocked in integration tests; tested in isolation in `test_health.py`.

---

Tests live in `backend/tests/` (outside `app/`); mypy runs only on `app/`.

**Why:** `--cov=app` measures only app code. Test files are not subject to mypy strict.

**How to apply:** Fixture return-type annotations in test files use `# type: ignore[misc]` for generator yields.

---

`pnl_repository.py` year-grouping uses `func.to_char(date, "YYYY")` (not `func.cast(extract(...), type_=None)`).

**Why:** `func.cast` returns `Cast[Any]` while `func.to_char` returns `Function[Any]`; mypy rejects mixed-type assignment in the `if period == "month": ... else: ...` branch. Both approaches produce string year labels.

**How to apply:** Always use `func.to_char(col, "YYYY")` for year bucketing in SQL aggregation.

---

API tests use `app.dependency_overrides[get_db]` to inject `AsyncMock` session.

**Why:** Routes call `Depends(get_db)` which is an async generator; override with async generator yielding `AsyncMock()`. Patch repo classes at their import path (e.g., `app.api.v1.uploads.UploadRepository`) so route handlers pick up the mock.

**How to apply:** Fixture sets override on `app.dependency_overrides[get_db]` and clears it after test. Use `patch("app.api.v1.<module>.<RepoClass>")` to mock repo methods.
