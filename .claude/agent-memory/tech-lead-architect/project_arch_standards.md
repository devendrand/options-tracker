---
name: Project Architecture Standards
description: Key architecture decisions, quality gates, and patterns for options-tracker v0.1
type: project
---

Options Tracker v0.1 is a single-user local Docker Compose app: Angular LTS frontend + Python 3.12/FastAPI backend + PostgreSQL 16.

**Why:** MVP1 scope — no auth, no external broker APIs, E*TRADE CSV only.
**How to apply:** Do not approve any plan that introduces auth middleware, broker API calls, or NgRx/Redux state management — all out of scope for v0.1.

## Quality Gates (non-negotiable)
- **100% line AND branch coverage** — both backend (pytest-cov) and frontend (jest). No exceptions per CLAUDE.md.
- TDD: tests written before implementation. Reject any plan without explicit test-first ordering.
- Backend: ruff check + ruff format + mypy must pass before tests run.
- Frontend: ESLint + Prettier + jest 100% + `ng build --production` must all pass.

## Backend Patterns
- SQLAlchemy 2.x async ORM; Alembic migrations
- `OptionsPositionLeg` join table (not single FKs) — supports scale-in and partial close
- `Transaction.quantity` is `Decimal` (not int) — fractional equity shares (D21)
- P&L sign convention: cash-flow positive=credit, negative=debit
- FIFO matching by `transaction_date` for same contract `(underlying, strike, expiry, option_type)`
- Dedup: Tier 2 composite key only for E*TRADE (no broker transaction ID)
- Internal transfers: `TRNSFR` prefix pairs flagged `is_internal_transfer=true`; orphans → PARSE_ERROR

## Frontend Patterns (F9 scaffold decisions)
- Standalone components (Angular 17+) — no NgModules
- OnPush change detection on all components
- Functional HTTP interceptors (`HttpInterceptorFn`)
- `ApiService` typed wrapper; error handling in `ErrorInterceptor` only (not in service)
- Lazy `loadComponent` routing (no feature modules)
- Jest + jest-preset-angular (no Karma)

## Common Review Watch-Points
- `RelativeDatePipe`: must use Angular `DatePipe` with UTC timezone param, NOT native `new Date()` — avoids ±1-day shift from browser timezone offset on date-only ISO strings
- `Sold Short`/`Bought To Cover` disambiguation: options vs equity via description regex — highest-risk classifier branch, requires at minimum 3 fixture examples per variant
- Assignment/Exercise: ALWAYS creates new `EquityPosition` lot; never merges with existing equity
- `parent_position_id` on `OptionsPosition`: reserved FK, not set in v0.1
- Covered call re-evaluation triggers: `EQUITY_BUY`, `OPTIONS_ASSIGNED`, `OPTIONS_EXERCISED`

## CRITICAL: Pydantic Alias + FastAPI Serialization (found in final review 2026-04-01)
FastAPI uses `by_alias=True` for `response_model` serialization by default.
- If a schema uses `Field(alias="col_name")`, the JSON key in the response is the **alias** (not the field name).
- **Confirmed bug in v0.1:** `EquityPositionResponse` declared `underlying: str = Field(alias="symbol")`. FastAPI emitted `"symbol"` in JSON; frontend `EquityPosition` expected `"underlying"` → equity display broken.
- **100% coverage did NOT catch this.** Tests checked Python attribute access and response counts, not JSON key names.
- **Rule for all future reviews:** API router tests MUST assert specific JSON field key names (e.g., `data["equity_items"][0]["symbol"]`), not just counts. Any schema with `Field(alias=...)` must have an HTTP-level key name assertion.
- Fix: prefer no alias — use consistent field names across ORM models, schemas, and TypeScript interfaces.
