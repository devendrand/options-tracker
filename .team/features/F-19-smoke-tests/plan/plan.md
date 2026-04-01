# F-19: End-to-End Smoke Test Suite — Plan

**Owner:** devops-qa-smoke-tester
**Status:** Done
**Depends on:** F-12, F-13, F-07, F-08, F-09, F-10, F-11

## Implementation Summary

**Implemented:** 2026-04-01

**Artifacts:**
- `smoke-tests/fixtures/covered_call.csv` — STO + BTC + EQUITY_BUY (covered call detection, P&L=248.70)
- `smoke-tests/fixtures/duplicate_upload.csv` — identical copy of covered_call.csv for dedup testing
- `smoke-tests/fixtures/long_call_expiry.csv` — BTO + Option Expired (P&L=-250.65)
- `smoke-tests/fixtures/assignment.csv` — STO PUT + Assigned (equity lot at strike)
- `smoke-tests/fixtures/partial_close.csv` — STO 2 contracts + BTC 1 contract (PARTIALLY_CLOSED)
- `smoke-tests/fixtures/equity_trades.csv` — EQUITY_BUY + EQUITY_SELL
- `smoke-tests/fixtures/dividends_transfers.csv` — DRIP pair + TRNSFR pair (internal_transfer_count=2)
- `smoke-tests/run_smoke_tests.py` — Python smoke test script (60+ assertions, 12 categories)
- `smoke-tests/requirements.txt` — `requests>=2.31.0`
- `.team/smoke-tests/README.md` — Execution guide, fixture reference, CI integration snippet

**How to run:**
```bash
cd smoke-tests && pip install -r requirements.txt
python run_smoke_tests.py [BASE_URL]
```

---

---

## CI/CD Validation Findings

### Task 1: CI Pipeline Review

#### backend-ci.yml — PASS with one finding

All required quality gates are present and correctly configured:

| Gate | Status | Notes |
|---|---|---|
| `ruff check .` | PASS | Correct working-directory: backend |
| `ruff format --check .` | PASS | Correct |
| `mypy app` | PASS | Correct |
| `pytest --cov=app --cov-fail-under=100 --cov-branch` | PASS | Also emits `--cov-report=xml` and `term-missing` |
| PostgreSQL 16 service container | PASS | Health check configured correctly |
| Python 3.12 | PASS | Matches CLAUDE.md and pyproject.toml |
| Poetry virtualenv caching | PASS | Keyed on `backend/poetry.lock` |
| Coverage artifact upload | PASS | 7-day retention |

**Finding B-1 (Low): `SECRET_KEY` env var in CI but not in .env.example**

The backend-ci.yml injects `SECRET_KEY: ci-test-secret-key` into the pytest step, but `app/core/config.py` does not define a `SECRET_KEY` field — it only defines `DATABASE_URL` and `LOG_LEVEL`. The `SECRET_KEY` env var is silently ignored (Pydantic `extra="ignore"`). This is harmless today but will create confusion when auth is added in v1.0. The `.env.example` also omits `SECRET_KEY`.

**Recommendation:** No action required for v0.1. When auth is added, add `SECRET_KEY` to both `config.py` and `.env.example` at that time.

---

#### frontend-ci.yml — PASS with one finding

All required quality gates are present:

| Gate | Status | Notes |
|---|---|---|
| ESLint via `npx ng lint` | PASS | Correct working-directory: frontend |
| Prettier check (`src/**/*.{ts,html,scss}`) | PASS | Correct |
| Jest with coverage (`--ci` flag) | PASS | `--ci` is correct for GitHub Actions |
| Production build | PASS | Runs after coverage — correct ordering |
| Node 20 | PASS | Angular LTS compatibility confirmed |
| npm ci caching | PASS | Keyed on `frontend/package-lock.json` |
| Coverage artifact upload | PASS | 7-day retention |

**Finding F-1 (Low): Frontend CI does not enforce coverage thresholds in the workflow — relies on jest.config.ts**

Coverage threshold enforcement (100% branches/functions/lines/statements) is correctly configured in `jest.config.ts` via `coverageThreshold`. The CI step runs `npx jest --coverage --ci` which will respect `jest.config.ts`. This is correct. No issue — documented for awareness only.

**Finding F-2 (Low): Node version pinned to "20" not "20.x" LTS**

The setup-node step uses `node-version: "20"` which resolves to the latest Node 20 patch. This is acceptable for v0.1 but consider pinning to `"20.x"` for deterministic builds if minor version drift becomes a concern in future.

---

#### docker-ci.yml — PASS with two findings

| Check | Status | Notes |
|---|---|---|
| Checkout | PASS | |
| Docker Buildx setup | PASS | |
| `docker compose build` | PASS | Both COMPOSE_DOCKER_CLI_BUILD and DOCKER_BUILDKIT set |

**Finding D-1 (Medium): docker-ci.yml only triggers on `main` branch**

`backend-ci.yml` and `frontend-ci.yml` both trigger on `main` and `develop` branches. `docker-ci.yml` only triggers on `main`. A broken Dockerfile introduced on `develop` will not be caught until the PR to `main`. 

**Recommendation:** Add `develop` to docker-ci.yml triggers:
```yaml
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
```

**Finding D-2 (Low): docker-ci.yml does not run `docker compose up` with a healthcheck probe**

The CI build step only runs `docker compose build` — it does not start containers or validate they reach a healthy state. A broken entrypoint, missing env var, or migration error would not be caught.

**Recommendation:** For F-19, add a `docker-smoke` job that runs `docker compose up -d`, waits for health, hits `/health`, and tears down. This plan covers that test case.

---

### Task 2: Docker Compose + Dockerfile Review

#### docker-compose.yml — PASS

| Check | Status | Notes |
|---|---|---|
| `db` service (postgres:16-alpine) | PASS | Correct version, volume, healthcheck |
| `backend` service | PASS | Depends on db with `service_healthy` condition |
| `frontend` service | PASS | Depends on backend with `service_healthy` condition |
| Healthchecks on all services | PASS | All three services have healthcheck blocks |
| Port bindings via env vars | PASS | `${BACKEND_PORT:-8000}`, `${FRONTEND_PORT:-4200}` |
| Bind mount for hot-reload | PASS | `./backend:/app` with node_modules exclusion on frontend |

**Note on `--reload` in development CMD:** `docker-compose.yml` overrides the backend CMD with `--reload`. The backend Dockerfile's production `CMD` does not include `--reload`. This is the correct pattern — dev gets reload, production image does not.

#### backend/Dockerfile — PASS

| Check | Status | Notes |
|---|---|---|
| Multi-stage build | PASS | builder + runtime stages |
| Production CMD without `--reload` | PASS | Correct |
| Dev dependencies excluded from runtime image | PASS | `poetry export --without dev` |
| No hardcoded secrets | PASS | |
| Healthcheck | NOT IN DOCKERFILE | Defined in docker-compose.yml instead — acceptable pattern |

**Finding BK-1 (Low): No `HEALTHCHECK` instruction in backend Dockerfile**

The healthcheck is defined in `docker-compose.yml` (curl to `/health`), not in the Dockerfile itself. This is acceptable for Docker Compose deployments. If the image is deployed standalone (e.g., Kubernetes), the healthcheck would need to be in the Dockerfile. Not a v0.1 blocker.

#### frontend/Dockerfile — PASS

| Check | Status | Notes |
|---|---|---|
| Two-stage build (dev + prod) | PASS | `dev` and `prod` targets |
| Dev stage serves via `ng serve` | PASS | `--poll 500` for bind mount compatibility |
| Prod stage runs `ng build --configuration production` | PASS | Correct |
| Prod stage serves via `serve` static server | PASS | Lightweight, correct |
| `npm ci --omit=dev` in prod stage | PASS | Dev dependencies excluded |
| `--disable-host-check` on dev serve | NOTE | Required for Docker, acceptable |

**Finding FK-1 (Low): `docker-compose.yml` does not specify `--target dev` for the frontend build**

The frontend Dockerfile has two targets (`dev` and `prod`). `docker-compose.yml` does not specify `target: dev` in the build block, so Docker Compose will build through all stages to the final `prod` stage by default. However, the `command` override in docker-compose (`npx ng serve ...`) effectively runs in dev mode regardless. The frontend container in development will install prod-only deps then re-run dev commands.

**Recommendation:** Add `target: dev` to the frontend build block in docker-compose.yml to avoid building the prod stage unnecessarily during local development:
```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
    target: dev
```

#### .env.example — PASS with one finding

| Variable | Present | Notes |
|---|---|---|
| `POSTGRES_USER` | YES | |
| `POSTGRES_PASSWORD` | YES | |
| `POSTGRES_DB` | YES | |
| `DATABASE_URL` | YES | Uses `db` hostname (matches docker-compose service name) |
| `LOG_LEVEL` | YES | |
| `BACKEND_PORT` | YES | |
| `FRONTEND_PORT` | YES | |

**Finding E-1 (Low): `SECRET_KEY` not in .env.example**

See Finding B-1. Not a v0.1 issue.

---

## Task 3: F-19 Smoke Test Suite Plan

### Overview

The smoke test suite validates the complete deployed stack against all critical user journeys derived from the PRD. Tests are designed to run in under 5 minutes, be fully environment-variable-driven, and provide a clear go/no-go signal before any environment promotion.

**Framework:** pytest + httpx (matches existing backend test tooling — no new dependencies)
**Test location:** `backend/tests/smoke/`
**Fixture CSV:** A minimal but complete E*TRADE CSV fixture covering all classification paths

### Execution Commands

```bash
# Start the stack
docker compose up -d

# Wait for all services to be healthy (manual or scripted)
docker compose ps

# Run smoke tests against the local stack
cd backend
DATABASE_URL=postgresql+asyncpg://options_tracker:options_tracker_dev@localhost:5432/options_tracker \
SMOKE_BASE_URL=http://localhost:8000 \
poetry run pytest tests/smoke/ -v --no-cov

# Tear down
docker compose down
```

---

## Test Categories

### Category 1: Container Health and Infrastructure

Validates that all Docker services start, pass their healthchecks, and accept connections. This must pass before any application-level tests run.

| Test ID | Description | Expected Result | Maps To |
|---|---|---|---|
| SMOKE-INF-01 | Backend `/health` endpoint responds | HTTP 200, `{"status": "ok"}` | Finding D-2, backend healthcheck |
| SMOKE-INF-02 | Frontend serves at port 4200 | HTTP 200 or 3xx on `http://localhost:4200` | docker-compose frontend healthcheck |
| SMOKE-INF-03 | Database accepts TCP connections on port 5432 | Connection succeeds without error | db service healthcheck |
| SMOKE-INF-04 | Backend `/docs` (OpenAPI) is accessible | HTTP 200 with `text/html` content type | FastAPI scaffold |
| SMOKE-INF-05 | Backend returns 404 with JSON body for unknown routes | HTTP 404, JSON response (not HTML) | FastAPI default error handling |

---

### Category 2: CSV Upload Flow (Happy Path)

Validates the primary user journey: upload a CSV, observe transactions and positions created, retrieve P&L. Uses a pre-built minimal E*TRADE fixture CSV that includes:
- One OPTIONS_SELL_TO_OPEN row
- One OPTIONS_BUY_TO_CLOSE row (closing the above)
- One EQUITY_BUY row
- One DIVIDEND row
- One OPTIONS_EXPIRED row

| Test ID | Description | Expected Result | Maps To |
|---|---|---|---|
| SMOKE-UPL-01 | POST valid E*TRADE CSV to `/api/v1/uploads` | HTTP 200, response contains `id` (UUID), `status: "active"`, `filename` | PRD Upload API |
| SMOKE-UPL-02 | GET `/api/v1/uploads` after upload | HTTP 200, list contains at least one entry with the upload ID from SMOKE-UPL-01 | F-12 |
| SMOKE-UPL-03 | GET `/api/v1/uploads/{id}` for the created upload | HTTP 200, upload detail includes transaction count > 0 | F-12 |
| SMOKE-UPL-04 | GET `/api/v1/transactions` after upload | HTTP 200, list is non-empty, entries include `category` field with valid enum values | F-13 |
| SMOKE-UPL-05 | GET `/api/v1/transactions?offset=0&limit=10` | HTTP 200, pagination params respected, `limit` not exceeded | F-13 pagination |
| SMOKE-UPL-06 | GET `/api/v1/positions` after upload | HTTP 200, list includes at least one options position with `status` field | F-13 |
| SMOKE-UPL-07 | GET `/api/v1/positions/{id}` for a matched position | HTTP 200, position detail includes `legs` array (non-empty) and `realized_pnl` field | F-13 position detail |
| SMOKE-UPL-08 | GET `/api/v1/pnl/summary` after upload | HTTP 200, response includes `realized_pnl` (numeric), at minimum the closed position is counted | F-13 P&L summary |
| SMOKE-UPL-09 | DELETE `/api/v1/uploads/{id}` (soft-delete) | HTTP 200 or 204, upload status changes to soft-deleted | F-12 |
| SMOKE-UPL-10 | GET `/api/v1/uploads/{id}` after soft-delete | HTTP 404 or upload `status` = `"soft_deleted"` (per API contract) | F-12 cascade |
| SMOKE-UPL-11 | GET `/api/v1/transactions` after soft-delete | Transactions from deleted upload no longer appear in active list | F-12 cascade |
| SMOKE-UPL-12 | GET `/api/v1/positions` after soft-delete | Positions from deleted upload no longer appear in active list | F-12 cascade |

---

### Category 3: Data Integrity and Domain Rules

Validates that the parser, classifier, matcher, and P&L engine produce correct output for specific edge cases defined in CLAUDE.md.

| Test ID | Description | Expected Result | Maps To |
|---|---|---|---|
| SMOKE-DAT-01 | Upload same CSV twice — duplicate detection | Second upload returns upload record, but duplicate transactions are flagged; transaction count in DB does not double | CLAUDE.md Deduplication (Tier 2 composite key) |
| SMOKE-DAT-02 | Upload CSV containing `Option Expired` row | Transaction created with `category: "OPTIONS_EXPIRED"` and `price: "0.00"` (not null, not parse error) | CLAUDE.md: "Option Expired — Price $ is blank in CSV; default to Decimal('0.00')" |
| SMOKE-DAT-03 | Upload CSV with matched CALL sell-to-open + buy-to-close pair | One `OptionsPosition` created with `status: "closed"`, `realized_pnl` = (open_amount + close_amount − commissions) | CLAUDE.md P&L formula |
| SMOKE-DAT-04 | FIFO matching: two open legs, one close leg | Close matches against the chronologically earliest open leg only; second open leg remains open | CLAUDE.md FIFO matching |
| SMOKE-DAT-05 | Upload CSV with `Sold Short` row where description matches options regex | Transaction classified as `OPTIONS_SELL_TO_OPEN`, not `EQUITY_SELL` | CLAUDE.md OQ5 / F-07 classifier |
| SMOKE-DAT-06 | Upload CSV with `Bought To Cover` row where description does NOT match options regex | Transaction classified as `EQUITY_BUY` (not an options category) | CLAUDE.md OQ5 / F-07 classifier |
| SMOKE-DAT-07 | Covered call detection: upload EQUITY_BUY (>=100 shares) then OPTIONS_SELL_TO_OPEN (short CALL on same underlying) | Short CALL position is stamped `is_covered_call: true` | CLAUDE.md Covered Call Detection |
| SMOKE-DAT-08 | `Bought To Open` / `Sold To Close` activity type variants produce correct categories | `Bought To Open` → `OPTIONS_BUY_TO_OPEN`, `Sold To Close` → `OPTIONS_SELL_TO_CLOSE` | CLAUDE.md OQ5 |
| SMOKE-DAT-09 | DIVIDEND rows (both DRIP positive and negative amounts) created as DIVIDEND category | Both rows stored with `category: "DIVIDEND"`, no equity position created for negative-amount row | CLAUDE.md OQ4 / F-06 |
| SMOKE-DAT-10 | Internal transfer pair (`TRNSFR` activity) stored with `is_internal_transfer: true`, excluded from analytics | Transfers do not appear in P&L summary | CLAUDE.md Internal Transfer Filtering |

---

### Category 4: Error Handling and Validation

Validates that the API rejects invalid input with well-formed error responses and does not corrupt database state.

| Test ID | Description | Expected Result | Maps To |
|---|---|---|---|
| SMOKE-ERR-01 | POST to `/api/v1/uploads` with a plain text file (not CSV) | HTTP 422 or 400 with structured JSON error body | F-12 input validation |
| SMOKE-ERR-02 | POST to `/api/v1/uploads` with an empty file (0 bytes) | HTTP 422 or 400, no upload record created in DB | F-12 input validation |
| SMOKE-ERR-03 | POST to `/api/v1/uploads` with a CSV missing required columns | HTTP 422 or 400, error body identifies the missing/malformed content | F-06 parser error handling |
| SMOKE-ERR-04 | GET `/api/v1/uploads/{id}` with a non-existent UUID | HTTP 404 with JSON error body | F-12 |
| SMOKE-ERR-05 | GET `/api/v1/positions/{id}` with a non-existent UUID | HTTP 404 with JSON error body | F-13 |
| SMOKE-ERR-06 | DELETE `/api/v1/uploads/{id}` with a non-existent UUID | HTTP 404 with JSON error body | F-12 |
| SMOKE-ERR-07 | GET `/api/v1/transactions?limit=501` (exceeds max) | HTTP 422, error indicates limit exceeded (max 500 per CLAUDE.md) | F-13 pagination limits |
| SMOKE-ERR-08 | POST to `/api/v1/uploads` with multipart form but missing `file` field | HTTP 422 with Pydantic validation error | F-12 FastAPI request validation |

---

### Category 5: API Contract and Pagination

Validates response shapes, pagination, and filtering parameters.

| Test ID | Description | Expected Result | Maps To |
|---|---|---|---|
| SMOKE-API-01 | GET `/api/v1/transactions` default pagination | `offset=0`, `limit=100` applied by default | CLAUDE.md API spec |
| SMOKE-API-02 | GET `/api/v1/transactions?limit=500` (at boundary) | HTTP 200, at most 500 results | CLAUDE.md API spec max limit=500 |
| SMOKE-API-03 | GET `/api/v1/positions` returns only options positions (not equity) | Response items all have `option_type` field or equivalent options-position shape | F-13 positions endpoint |
| SMOKE-API-04 | P&L summary response shape | Contains `realized_pnl` at minimum; is a valid JSON object with numeric values | F-13 pnl/summary |

---

## Smoke Test Fixture Design

### Minimal E*TRADE CSV Fixture

The fixture at `backend/tests/smoke/fixtures/etrade_smoke.csv` must produce all classification categories needed to exercise the above tests. Required rows (in addition to standard preamble/header per CLAUDE.md parsing rules):

```
Row type                        Category produced
──────────────────────────────────────────────────────────
Bought To Open (options)        OPTIONS_BUY_TO_OPEN
Sold To Close (options)         OPTIONS_SELL_TO_CLOSE
Sold Short + options desc       OPTIONS_SELL_TO_OPEN
Bought To Cover + options desc  OPTIONS_BUY_TO_CLOSE
Sold Short + equity desc        EQUITY_SELL
Option Expired (blank price)    OPTIONS_EXPIRED
Buy (equity, ≥100 shares)       EQUITY_BUY
Dividend (positive)             DIVIDEND
Dividend (negative, DRIP debit) DIVIDEND
Transfer TRNSFR (paired pair)   stored, is_internal_transfer=true
```

The CSV must be valid E*TRADE format:
- Rows 1–6 are preamble (skipped)
- Row 7 is the header
- Trailing blank/disclaimer rows at the end

---

## Execution Prerequisites

Before running smoke tests, the following must be true:

- [ ] `docker compose up -d` completed without error
- [ ] All three containers (`db`, `backend`, `frontend`) report `healthy` in `docker compose ps`
- [ ] Alembic migrations have run (either via `docker compose up` entrypoint or manual `alembic upgrade head`)
- [ ] `.env` file exists and contains all variables from `.env.example`
- [ ] No stale data in the database from prior smoke runs (run `docker compose down -v && docker compose up -d` for clean state)

---

## Go / No-Go Criteria

| Category | Required pass rate |
|---|---|
| Category 1 (Infrastructure) | 5 / 5 — any failure is a hard block |
| Category 2 (Upload Flow) | 12 / 12 — any failure is a hard block |
| Category 3 (Data Integrity) | 10 / 10 — any failure is a hard block |
| Category 4 (Error Handling) | 8 / 8 — any failure is a hard block |
| Category 5 (API Contract) | 4 / 4 — any failure is a hard block |
| **Total** | **39 / 39** |

**No partial promotion is acceptable.** All 39 tests must pass before F-19 can be marked DONE and before any deployment to a staging or production environment.

---

## Open Issues to Resolve Before Implementation

1. **API response shape for soft-deleted upload**: SMOKE-UPL-10 checks behavior after DELETE. The API contract must specify whether DELETE returns 404 on re-GET or returns the record with `status="soft_deleted"`. This must be resolved in F-12.

2. **Alembic migration entrypoint**: It is not yet defined whether `docker compose up` auto-runs `alembic upgrade head`. The smoke test setup script must account for this. Recommended: add a `command` override or a dedicated init container in docker-compose.yml that runs migrations before the backend starts.

3. **Covered call re-evaluation trigger**: SMOKE-DAT-07 requires uploading equity first, then options. The test must upload two separate CSVs in sequence or a single CSV where equity appears before the options row chronologically. Confirm with F-11 implementer which upload ordering triggers re-evaluation.

---

## CI Integration (Post-Implementation)

Once implemented, the smoke test job should be added to `docker-ci.yml` as a second job:

```yaml
smoke:
  needs: build
  runs-on: ubuntu-latest
  steps:
    - name: Checkout
      uses: actions/checkout@v4
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    - name: Copy .env
      run: cp .env.example .env
    - name: Start stack
      run: docker compose up -d
    - name: Wait for backend healthy
      run: |
        for i in $(seq 1 30); do
          curl -sf http://localhost:8000/health && break
          sleep 5
        done
    - name: Run smoke tests
      run: |
        cd backend
        poetry install --no-interaction
        poetry run pytest tests/smoke/ -v --no-cov
    - name: Tear down
      if: always()
      run: docker compose down -v
```

This job should run on the same trigger branches as `docker-ci.yml` (with Finding D-1 fix applied: `main` and `develop`).
