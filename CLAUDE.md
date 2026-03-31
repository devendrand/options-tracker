# Options Tracker — Claude Project Guide

## Project Overview

Options Tracker is a web application for individual investors to upload E*TRADE brokerage CSV exports, parse and classify options trades, match open/close legs, and compute realized P&L. Non-options activity is retained for record-keeping but excluded from analytics.

**Current version:** v0.1 (MVP1) — E*TRADE CSV only, single-user, local Docker deployment.

**PRD:** `PRD.md` (authoritative source for all requirements and resolved decisions)

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Angular (latest LTS) + TypeScript |
| Backend | Python 3.12 + FastAPI + Pydantic |
| Database | PostgreSQL 16 |
| ORM / Migrations | SQLAlchemy 2.x (async) + Alembic |
| Containerisation | Docker + Docker Compose |
| CI | GitHub Actions |

**Backend tooling:** Poetry, Ruff (lint + format), mypy, pytest, pytest-cov, pytest-asyncio, httpx, factory-boy  
**Frontend tooling:** Angular CLI, ESLint + @angular-eslint, Prettier, Jest + jest-preset-angular

---

## Project Structure

```
options-tracker/
├── PRD.md
├── CLAUDE.md
├── docker-compose.yml
├── .env.example
├── .github/workflows/
│   ├── backend-ci.yml
│   └── frontend-ci.yml
├── backend/
│   ├── pyproject.toml          # Poetry, Ruff, mypy config
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── api/v1/             # uploads.py, transactions.py, positions.py
│       ├── core/               # config.py, database.py
│       ├── models/             # SQLAlchemy ORM models
│       ├── schemas/            # Pydantic schemas
│       ├── services/
│       │   ├── parser/         # etrade.py (broker adapters)
│       │   ├── classifier.py
│       │   ├── deduplicator.py
│       │   ├── matcher.py      # FIFO open/close matching
│       │   └── pnl.py
│       ├── repositories/
│       └── tests/
│           ├── unit/
│           └── integration/
└── frontend/
    ├── angular.json
    ├── package.json
    └── src/app/
        ├── core/
        ├── features/           # dashboard, upload, transactions, positions
        └── shared/
```

---

## Development Workflow

### Local setup
```bash
cp .env.example .env
docker compose up --build
# Frontend: http://localhost:4200
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
# DB:       localhost:5432
```

### Backend commands (run inside `backend/`)
```bash
poetry install
poetry run ruff check .
poetry run ruff format .
poetry run mypy app
poetry run pytest --cov=app --cov-fail-under=100 --cov-branch
```

### Frontend commands (run inside `frontend/`)
```bash
npm ci
ng lint
npx prettier --check .
npx jest --coverage
ng build --configuration production
```

---

## Key Domain Rules

### E*TRADE CSV Parsing
- **Preamble:** Skip rows 1–6; header is row 7; skip trailing blank/disclaimer rows.
- **Sentinel:** `--` means null — treat as `None` for all fields.
- **Dates:** `MM/DD/YY` → `datetime.date`, 2-digit year = 20YY.
- **Commission:** Default to `Decimal('0.00')` when blank; all other numeric fields default to `None`.
- **Quantity:** Store as absolute value on `Transaction`; direction encoded in `category`. Options quantities are whole numbers; equity quantities may be fractional (`Decimal`).
- **Options detection regex:** `^(CALL|PUT)\s+(\S+)\s+(\d{2}/\d{2}/\d{2})\s+([\d.]+)`
- `Sold Short` / `Bought To Cover` require description-field regex to disambiguate options vs equity.
- `Option Expired` — `Price $` is blank in CSV; default to `Decimal('0.00')`, not a parse error.

### Transaction Classification
Options categories: `OPTIONS_SELL_TO_OPEN`, `OPTIONS_BUY_TO_OPEN`, `OPTIONS_BUY_TO_CLOSE`, `OPTIONS_SELL_TO_CLOSE`, `OPTIONS_EXPIRED`, `OPTIONS_ASSIGNED`, `OPTIONS_EXERCISED`  
Equity/other: `EQUITY_BUY`, `EQUITY_SELL`, `DIVIDEND`, `TRANSFER`, `INTEREST`, `FEE`, `JOURNAL`, `OTHER`

### Deduplication (E*TRADE — Tier 2 composite key only)
Key: `(trade_date, transaction_date, settlement_date, activity_type, description, symbol, quantity, price, amount, commission)`  
- Exact match → `DUPLICATE` (first upload wins)  
- Collision → `POSSIBLE_DUPLICATE` (surfaced for user review)

### Internal Transfer Filtering
Paired `TRNSFR` rows (Activity Type = `Transfer`, description starts with `TRNSFR`) are stored as `RawTransaction` with `is_internal_transfer = true` but excluded from analytics. Orphaned legs → `PARSE_ERROR`.

### P&L Sign Convention (cash-flow)
- Positive amount = cash credited (premium received, sale proceeds)
- Negative amount = cash debited (premium paid, purchase cost)
- Formula: `Realized P&L = Open Amount + Close Amount − |open_commission| − |close_commission|`
- Open/Close Amount = `price × 100 × quantity` (signed per cash-flow convention)

### Position Matching
- FIFO: oldest open leg matched to earliest close leg for same contract `(underlying, strike, expiry, option_type)`.
- `OptionsPositionLeg` join table (not single FKs) — supports scale-in and partial close.
- Assignment/Exercise: always create a separate `EquityPosition` lot; never merge with existing equity.

### Covered Call Detection
- Stamped at position-creation time; re-evaluated after any upload with `EQUITY_BUY`, `OPTIONS_ASSIGNED`, or `OPTIONS_EXERCISED`.
- Short CALL is covered if user holds ≥ 100 shares per contract of the underlying.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/uploads` | Upload CSV (broker implicit E*TRADE in v0.1) |
| `GET` | `/api/v1/uploads` | List uploads |
| `GET` | `/api/v1/uploads/{id}` | Upload detail |
| `DELETE` | `/api/v1/uploads/{id}` | Soft-delete with cascade |
| `GET` | `/api/v1/transactions` | List transactions (filterable, paginated) |
| `GET` | `/api/v1/positions` | List options positions (filterable, paginated) |
| `GET` | `/api/v1/positions/{id}` | Position detail with legs and P&L |
| `GET` | `/api/v1/pnl/summary` | Aggregated realized P&L |

All list endpoints: `?offset=0&limit=100` (max `limit=500`).

---

## Quality Gates (CI-enforced)

- **100% line and branch coverage** — both backend and frontend; no exceptions.
- **TDD** — tests written before implementation.
- **Backend:** `ruff check` + `ruff format --check` + `mypy app` must all pass before tests.
- **Frontend:** ESLint + Prettier check + Jest 100% coverage + production build must all pass.

---

## Out of Scope in v0.1

- Multi-user auth (planned v1.0)
- Broker API integrations (CSV upload only)
- Real-time pricing / Greeks
- Tax lot accounting
- Roll-chain tracking (`parent_position_id` is reserved FK)
- Multi-leg strategy grouping
- Broker auto-detection

---

## Open Questions (PRD §11)

1. Equity P&L in v0.1 — include or defer?
2. Partially-closed position UI layout
3. P&L summary: simultaneous month+year or one at a time?
4. DRIP dividend handling (paired debit/credit rows)
5. Confirm `Bought To Open` / `Sold To Close` activity type support alongside `Sold Short` / `Bought To Cover`
