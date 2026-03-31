# Options Tracker v0.1 — Prioritized Feature Backlog

**Version:** 0.1 (MVP1)
**Date:** 2026-03-30
**BA:** business-analyst
**Status:** Approved for implementation

---

## MoSCoW Summary

| Priority | Count | Features |
|---|---|---|
| Must Have | 11 | Core infrastructure, upload pipeline, classification, dedup, position matching, P&L, API, CI |
| Should Have | 4 | Equity P&L, covered call detection, upload soft-delete, UI pages |
| Could Have | 2 | P&L summary filter by underlying, partial-close drawer UX |
| Won't Have | 5 | Auth, broker API, real-time pricing, roll-chain, multi-leg strategy grouping |

---

## Implementation Order & Feature Details

Dependencies flow top-to-bottom. Features within the same tier can be parallelized where ownership differs.

---

### Tier 0 — Project Scaffold (Unblocks everything)

---

#### F-01: Docker Compose + Environment Scaffold
**Priority:** Must Have
**Owner:** devops-qa-smoke-tester
**Dependencies:** None

**Description:** Create `docker-compose.yml`, `.env.example`, and service definitions for backend (FastAPI), frontend (Angular), and database (PostgreSQL 16). Wire up healthchecks and volume mounts for local development.

**Acceptance Criteria:**
- `docker compose up --build` starts all three services with no manual steps beyond `cp .env.example .env`
- Backend reachable at `localhost:8000`, frontend at `localhost:4200`, DB at `localhost:5432`
- `.env.example` includes `DATABASE_URL`, `POSTGRES_*`, `LOG_LEVEL` variables
- All services pass healthchecks before dependent services start
- No credentials committed to source control

---

#### F-02: Backend Project Scaffold (Poetry + FastAPI + Alembic)
**Priority:** Must Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-01

**Description:** Initialize `backend/` with Poetry, FastAPI application skeleton (`main.py`, `core/config.py`, `core/database.py`), Alembic setup, and CI tooling config (Ruff, mypy, pytest-cov).

**Acceptance Criteria:**
- `poetry install` succeeds cleanly
- `poetry run ruff check .` and `poetry run ruff format --check .` pass on the scaffold
- `poetry run mypy app` passes with no errors
- `poetry run pytest --cov=app --cov-fail-under=100` passes (100% coverage on empty scaffold)
- FastAPI app starts and `GET /docs` returns 200
- Alembic `env.py` connects to the PostgreSQL DB from `DATABASE_URL`

---

#### F-03: Frontend Project Scaffold (Angular + Jest + ESLint)
**Priority:** Must Have
**Owner:** angular-tdd-frontend
**Dependencies:** F-01

**Description:** Initialize `frontend/` with Angular CLI (latest LTS), configure Jest (replacing Karma) via `jest-preset-angular`, ESLint with `@angular-eslint`, and Prettier. Set up Angular routing skeleton and feature module structure.

**Acceptance Criteria:**
- `npm ci` succeeds
- `ng lint` passes on scaffold
- `npx prettier --check .` passes
- `npx jest --coverage` passes with 100% coverage gate configured
- `ng build --configuration production` produces a clean build
- Angular app loads at `localhost:4200` with a placeholder home route

---

#### F-04: GitHub Actions CI Pipelines
**Priority:** Must Have
**Owner:** devops-qa-smoke-tester
**Dependencies:** F-02, F-03

**Description:** Create `.github/workflows/backend-ci.yml` and `.github/workflows/frontend-ci.yml` implementing all CI steps from PRD §7. Add Docker build CI job.

**Acceptance Criteria:**
- Backend CI: ruff check → ruff format → mypy → pytest 100% coverage → artifact upload
- Frontend CI: npm ci → ng lint → prettier check → jest 100% coverage → ng build production
- Docker CI: `docker compose build` passes
- Pipelines trigger on push and PR to `main` and `develop`
- All jobs pass on initial scaffold commit

---

### Tier 1 — Database Schema (Unblocks all backend services)

---

#### F-05: Database Schema + Alembic Migrations
**Priority:** Must Have
**Owner:** postgres-alembic-dev
**Dependencies:** F-02

**Description:** Create all SQLAlchemy ORM models and the initial Alembic migration for the complete v0.1 schema: `Upload`, `RawTransaction`, `Transaction`, `OptionsPosition`, `OptionsPositionLeg`, `EquityPosition`. Include all required indexes from PRD §4.

**Acceptance Criteria:**
- `alembic upgrade head` creates all tables cleanly against a fresh PostgreSQL 16 instance
- `alembic downgrade base` cleanly reverses all migrations
- All models include soft-delete fields (`status`, `deleted_at`) where specified in PRD
- Required indexes created: `transactions(upload_id, symbol, category, transaction_date)`, `options_positions(underlying, status, expiry)`
- `OptionsPositionLeg` join table supports multiple open and close legs per position
- `EquityPosition.assigned_position_id` FK nullable, `parent_position_id` on `OptionsPosition` nullable (reserved)
- `Transaction.quantity` stored as `Decimal` to support fractional equity shares (D21)
- 100% test coverage on model definitions and migration scripts

---

### Tier 2 — Backend Services (Can parallelize F-06 through F-10)

---

#### F-06: E*TRADE CSV Parser
**Priority:** Must Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-05

**Description:** Implement `app/services/parser/etrade.py` — the E*TRADE adapter that transforms a raw CSV file into a list of `ParsedTransaction` objects per the full specification in PRD §3.1.2, §3.2.1, §3.2.2, and §5.6.

**Acceptance Criteria:**
- Skips preamble rows 1–6; parses header from row 7; skips trailing blank/disclaimer rows
- All 13 column headers validated; `FileValidationError` raised if any missing
- `--` sentinel treated as `None` for all fields
- Dates parsed as `MM/DD/YY` → `datetime.date` with 20YY year expansion
- `Commission` defaults to `Decimal('0.00')` when blank; all other numeric fields default to `None`
- Quantity stored as absolute value; direction captured for classification
- Options description regex correctly extracts `option_type`, `underlying`, `expiry`, `strike` from all variants (CALL, PUT, variable whitespace, index tickers like SPXW)
- `Option Expired` blank `Price $` defaults to `Decimal('0.00')` — not a parse error
- Both `Sold Short`/`Bought To Cover` AND `Bought To Open`/`Sold To Close` activity types handled correctly (OQ5)
- Internal transfer pairs detected and flagged `is_internal_transfer=True`; orphaned legs → `PARSE_ERROR`
- 100% line and branch coverage including all edge cases

---

#### F-07: Transaction Classifier
**Priority:** Must Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-06

**Description:** Implement `app/services/classifier.py` — maps `ParsedTransaction` objects to internal `TransactionCategory` enum values per the full mapping table in PRD §3.2.1.

**Acceptance Criteria:**
- All 17 `Activity Type` values in the mapping table produce the correct `TransactionCategory`
- `Sold Short` / `Bought To Cover` disambiguation uses description-field regex (options vs equity)
- `Bought To Open` → `OPTIONS_BUY_TO_OPEN`; `Sold To Close` → `OPTIONS_SELL_TO_CLOSE` (unambiguous, no regex needed)
- `Transfer` rows with non-`TRNSFR` descriptions classify as `OTHER`
- `OTHER` category used for any unrecognised `Activity Type` value
- Unit tests cover every mapping row including both disambiguation paths for `Sold Short`/`Bought To Cover`
- 100% branch coverage

---

#### F-08: Deduplication Service
**Priority:** Must Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-05, F-07

**Description:** Implement `app/services/deduplicator.py` — Tier 2 composite-key deduplication for E*TRADE transactions per PRD §3.1.3.

**Acceptance Criteria:**
- Composite key: `(trade_date, transaction_date, settlement_date, activity_type, description, symbol, quantity, price, amount, commission)`
- Exact match → `status = DUPLICATE`; first-upload record wins
- Same composite key from a different upload context (e.g. different upload ID but same key) → `status = POSSIBLE_DUPLICATE`
- `POSSIBLE_DUPLICATE` records are not auto-suppressed; surfaced for user review on Upload History page
- New transaction with no existing match → `status = ACTIVE`
- Integration tests cover cross-upload dedup scenarios
- 100% coverage

---

#### F-09: Options Position Matcher (FIFO)
**Priority:** Must Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-05, F-07

**Description:** Implement `app/services/matcher.py` — FIFO open/close position matching for options transactions per PRD §3.3.

**Acceptance Criteria:**
- Matches by contract identity: `(underlying_symbol, strike_price, expiry_date, option_type)`
- FIFO: oldest open leg matched to earliest close leg
- Creates `OptionsPositionLeg` records for each open/close leg; supports scale-in (multiple open legs) and partial close
- Position status correctly set: `OPEN`, `PARTIALLY_CLOSED`, `CLOSED` based on quantity math
- `OPTIONS_EXPIRED` / `OPTIONS_ASSIGNED` / `OPTIONS_EXERCISED` correctly close positions
- Assignment/Exercise creates a new `EquityPosition` with `source=ASSIGNMENT|EXERCISE` and `cost_basis=strike_price`; never merged with existing equity lots
- Rolling positions (BTC + new STO) create two independent positions; `parent_position_id` not set in v0.1
- 100% coverage including partial close, scale-in, and expiry scenarios

---

#### F-10: P&L Calculation Service
**Priority:** Must Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-09

**Description:** Implement `app/services/pnl.py` — P&L calculation for closed options positions and (Should Have) closed equity positions per PRD §3.5.

**Acceptance Criteria:**
- Options P&L formula: `Open Amount + Close Amount − |open_commission| − |close_commission|` where amounts = `price × 100 × quantity` (cash-flow signed)
- Partial close: P&L calculated on FIFO-matched closed portion only; open portion contributes 0 realized P&L
- Worthless expiry: close amount = $0.00, close commission = $0.00
- Equity P&L formula: `(sell_price − cost_basis_per_share) × quantity_sold` (per OQ1 resolution)
- `EQUITY_SELL` closes `EquityPosition` records (FIFO by `created_at` if multiple lots); sets `equity_realized_pnl` and `status=CLOSED`
- P&L aggregation: by position, by underlying, by calendar month, by calendar year
- 100% coverage including covered call, CSP, long call expiry, partial close, equity sell scenarios

---

#### F-11: Covered Call Detection
**Priority:** Should Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-09, F-05

**Description:** Implement covered call stamping at position-creation time and re-evaluation trigger per PRD §3.3.5.

**Acceptance Criteria:**
- `is_covered_call = True` stamped on `OptionsPosition` at creation if user holds ≥ 100 shares × contract quantity of the underlying at that moment
- Equity holdings queried from `EquityPosition` records (status=OPEN, same underlying)
- Re-evaluation triggered after any upload containing `EQUITY_BUY`, `OPTIONS_ASSIGNED`, or `OPTIONS_EXERCISED` transactions for the same underlying
- Re-evaluation updates all OPEN short CALL positions for that underlying
- 100% coverage including edge: exactly 100 shares (covered), 99 shares (not covered), assignment creates 100 shares triggering re-evaluation

---

### Tier 3 — API Endpoints (Can parallelize F-12 and F-13)

---

#### F-12: Upload API Endpoints
**Priority:** Must Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-06, F-07, F-08, F-09, F-10

**Description:** Implement the full upload processing pipeline behind `POST /api/v1/uploads` and related upload endpoints per PRD §6 and §3.1.

**Acceptance Criteria:**
- `POST /api/v1/uploads`: accepts multipart CSV, validates file (size ≤ 10MB, rows ≤ 10,000, headers present), runs full pipeline (parse → classify → dedup → match → P&L), returns upload summary
- File exceeding size/row limits returns 422 with specific error message; no DB writes occur
- Upload summary response includes: `rows_parsed`, `options_count`, `duplicate_count`, `possible_duplicate_count`, `parse_error_count`, `internal_transfer_count`
- `GET /api/v1/uploads`: paginated list with `date_from`, `date_to` filters; default `limit=100`, max `limit=500`
- `GET /api/v1/uploads/{id}`: upload detail with full row count breakdown
- `DELETE /api/v1/uploads/{id}`: soft-delete with cascade; positions with only one leg from this upload → soft-deleted; positions straddling two uploads → reverted to OPEN; returns warning message about possible duplicate resurfacing
- 10,000 row file processes in under 10 seconds (NFR)
- 100% coverage including all error paths

---

#### F-13: Transactions + Positions + P&L API Endpoints
**Priority:** Must Have
**Owner:** backend-tdd-api-dev
**Dependencies:** F-12

**Description:** Implement read endpoints for transactions, positions, and P&L summary per PRD §6.

**Acceptance Criteria:**
- `GET /api/v1/transactions`: filterable by `category`, `status`, `symbol`, `upload_id`, `date_from`, `date_to`; sortable by `sort_by`/`sort_dir`; paginated
- `GET /api/v1/positions`: filterable by `status`, `underlying`, `option_type`, `expiry_from`, `expiry_to`; sortable; paginated; default shows options positions
- `GET /api/v1/positions/{id}`: position detail including all `OptionsPositionLeg` records with transaction dates, quantities, prices, and P&L breakdown per leg
- `GET /api/v1/pnl/summary?period=month|year&underlying=...`: returns array of `{period_label, options_pnl, equity_pnl, total_pnl}` sorted chronologically
- All list endpoints support `offset`/`limit` with max `limit=500`
- 100% coverage including empty result sets and filter combinations

---

### Tier 4 — Frontend UI

---

#### F-14: Angular Core Services + HTTP Client Setup
**Priority:** Must Have
**Owner:** angular-tdd-frontend
**Dependencies:** F-03, F-12, F-13

**Description:** Create Angular core services (Upload service, Transaction service, Position service, P&L service) with typed HTTP clients matching the backend API contracts. Configure `HttpClientModule`, environment-based API base URL, and error interceptor.

**Acceptance Criteria:**
- Each service has a corresponding spec file with 100% coverage
- Services use strongly-typed Pydantic-matching TypeScript interfaces for all request/response shapes
- Error interceptor surfaces API error messages to a global notification/toast service
- Environment files configured for `localhost:8000` (development) and production
- Services are injectable and tree-shakeable

---

#### F-15: Upload Page
**Priority:** Must Have
**Owner:** angular-tdd-frontend
**Dependencies:** F-14

**Description:** Implement the Upload feature module — file picker with drag-and-drop, upload progress, and post-upload summary display per PRD §3.7.

**Acceptance Criteria:**
- File picker supports drag-and-drop and click-to-browse; accepts `.csv` files only (client-side filter)
- Upload progress indicator shown during `POST /api/v1/uploads`
- Post-upload summary card shows: rows parsed, options found, duplicates detected, internal transfers filtered, parse errors
- Parse errors and possible duplicates shown with a link to the Transactions page filtered to that upload
- File size validation feedback shown before upload (client-side check ≤ 10MB)
- Broker label shows "E*TRADE" (implicit in MVP1 — no broker selector)
- 100% Jest coverage

---

#### F-16: Transactions Page
**Priority:** Must Have
**Owner:** angular-tdd-frontend
**Dependencies:** F-14

**Description:** Implement the Transactions feature module — paginated, filterable, sortable table of all transactions per PRD §3.7.

**Acceptance Criteria:**
- Table columns: Date, Activity Type, Description, Symbol, Category, Qty, Price, Amount, Commission, Status, Upload
- Filters: category (multi-select), status (multi-select), symbol (text), date range
- Pagination: 100 rows per page default; page size selector
- `DUPLICATE` and `POSSIBLE_DUPLICATE` rows visually distinguished (row color or badge)
- `PARSE_ERROR` rows shown with an error indicator
- Upload column links to upload detail
- 100% Jest coverage

---

#### F-17: Positions Page + Dashboard
**Priority:** Must Have
**Owner:** angular-tdd-frontend
**Dependencies:** F-14

**Description:** Implement the Positions feature module and Dashboard per PRD §3.7. Positions page shows one row per `OptionsPosition` with an expandable detail drawer for legs (OQ2 resolution).

**Acceptance Criteria (Positions Page):**
- Table columns: Underlying, Option Type, Strike, Expiry, Direction, Status, Open Qty, Closed Qty, Realized P&L (closed portion), Covered Call indicator
- Filters: status, underlying, option type, expiry range
- `PARTIALLY_CLOSED` badge on partially-closed rows
- Expandable drawer: loads `GET /api/v1/positions/{id}` on expand; shows each leg with date, role (OPEN/CLOSE), qty, price, cash amount
- 100% Jest coverage

**Acceptance Criteria (Dashboard):**
- Summary cards: Total Realized P&L (options + equity combined), Open Positions count, Closed Positions count, Recent Uploads (last 5)
- P&L card shows positive/negative with colour coding
- Recent uploads list links to upload detail

---

#### F-18: Upload History Page + P&L Summary Page
**Priority:** Should Have
**Owner:** angular-tdd-frontend
**Dependencies:** F-14

**Description:** Implement Upload History page and P&L Summary page per PRD §3.7 and OQ3 resolution.

**Acceptance Criteria (Upload History):**
- List of all uploads: timestamp, filename, broker, rows parsed, options count, duplicates, parse errors, internal transfers
- Soft-delete button with confirmation dialog showing the duplicate-resurfacing warning
- `POSSIBLE_DUPLICATE` count links to filtered Transactions page
- 100% Jest coverage

**Acceptance Criteria (P&L Summary):**
- Period toggle: Month / Year (default: Year)
- Table: period label, options P&L, equity P&L, total P&L — sorted chronologically
- Optional underlying filter (text input, clears to show all underlyings)
- Positive P&L in green, negative in red
- 100% Jest coverage

---

### Tier 5 — QA + Smoke Tests

---

#### F-19: End-to-End Smoke Test Suite
**Priority:** Must Have
**Owner:** devops-qa-smoke-tester
**Dependencies:** F-12, F-13, F-15, F-16, F-17

**Description:** Create smoke tests that validate the full upload-to-display pipeline against a running Docker Compose environment using representative E*TRADE CSV test fixtures.

**Acceptance Criteria:**
- Smoke test fixtures include: covered call (STO + BTC), long call (BTO + expiry worthless), assignment, partial close, equity buy + sell, DRIP dividend pair, internal transfer pair, duplicate upload
- `POST /api/v1/uploads` with each fixture returns expected summary counts
- `GET /api/v1/positions` returns correctly matched and classified positions
- `GET /api/v1/pnl/summary` returns correct P&L figures matching manual calculations
- Smoke tests runnable via `docker compose run` or separate script; documented in `.team/smoke-tests/`
- CI smoke test job configured to run against `docker compose up` environment

---

## Won't Have in v0.1

| Feature | Reason | Target Version |
|---|---|---|
| Multi-user authentication (JWT) | Single-user local deployment; planned v1.0 | v1.0 |
| Broker API integrations | CSV-only in MVP; adapter pattern already in architecture | v0.2+ |
| Real-time options pricing / Greeks | No external data feed; out of scope | v1.0+ |
| Roll-chain tracking (`parent_position_id`) | Field reserved; UI/logic deferred | v1.0 |
| Multi-leg strategy grouping (spreads, condors) | Independent legs tracked; strategy grouping deferred | v1.0 |

---

## Dependency Graph (Summary)

```
F-01 (Docker) ──► F-02 (Backend scaffold) ──► F-05 (DB schema)
                                                    ├──► F-06 (Parser)
                                                    │      └──► F-07 (Classifier)
                                                    │              ├──► F-08 (Dedup)
                                                    │              └──► F-09 (Matcher) ──► F-10 (P&L)
                                                    │                                         └──► F-11 (Covered call)
                                                    └──► F-12 (Upload API) ─────────────────────────────────►
                                                           └──► F-13 (Tx/Pos/PnL API)
              ──► F-03 (Frontend scaffold) ──► F-14 (Angular services) ──► F-15/F-16/F-17/F-18 (UI pages)
F-01 ──► F-04 (CI pipelines)
F-15..F-17 ──► F-19 (Smoke tests)
```

---

## Risks & Flags

1. **DRIP dividend equity creation (deferred):** DRIP debit rows create fractional equity lots that are currently untracked. If the user has significant DRIP activity, their equity holdings (and therefore covered call detection) will be slightly understated. Flag to user in UI: "DRIP share purchases are tracked as dividends in v0.1. Covered call detection may not reflect DRIP-acquired shares." (v1.0 backlog item)

2. **Partial close UI complexity:** The expandable drawer in F-17 requires lazy loading position detail on expand — ensure the Angular implementation handles the async state cleanly (loading spinner, error state) to avoid a brittle UX.

3. **`Sold Short` / `Bought To Cover` test coverage:** These disambiguation paths are the highest-risk classifier branches. The parser and classifier unit tests must include fixtures for both the options AND equity variants of each activity type, with at least 3 concrete description examples per variant.

4. **Upload processing performance:** The 10-second NFR for 10,000-row files requires async processing with efficient bulk-insert patterns. The backend team should validate this with a load test before declaring F-12 complete.

5. **Fractional quantity (D21):** `Transaction.quantity` is `Decimal` (not integer). This was a late decision (D21 in resolved decisions). The matcher must handle fractional quantities correctly for equity lots. Ensure this is covered in unit tests for `matcher.py` and `pnl.py`.
