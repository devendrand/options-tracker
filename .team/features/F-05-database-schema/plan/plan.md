# F-05: Database Schema + Alembic Migrations — Implementation Plan

**Owner:** postgres-alembic-dev  
**Date:** 2026-03-30  
**Status:** In Progress

---

## Objective

Create all SQLAlchemy 2.x ORM models, a single Alembic initial migration, and full unit test coverage for the options-tracker v0.1 schema.

---

## Files to Create

```
backend/app/models/
  enums.py                  ← all Python Enum classes (shared across models)
  upload.py                 ← Upload ORM model
  raw_transaction.py        ← RawTransaction ORM model
  transaction.py            ← Transaction ORM model
  options_position.py       ← OptionsPosition ORM model
  options_position_leg.py   ← OptionsPositionLeg ORM model
  equity_position.py        ← EquityPosition ORM model
  __init__.py               ← re-exports all models so Alembic autoimport works

backend/alembic/versions/
  20260330_a1b2c3d4e5f6_initial_schema.py  ← hand-written initial migration

backend/tests/unit/
  test_models.py            ← 100% coverage on all model files
```

---

## Schema Design Decisions

### Primary Keys
All tables use `UUID` primary keys generated via `uuid.uuid4()` server-side default in Python. This avoids sequential integer guessing and is safe for future distribution.

### Enums → PostgreSQL ENUM types
All status/category enums are stored as PostgreSQL native ENUM types (not VARCHAR + CHECK constraint). This provides:
- Type safety at the DB level
- Compact storage
- Readable pg_dump output

Enum names follow `snake_case` convention matching the column/concept name:
- `upload_status`, `raw_transaction_status`, `transaction_status`
- `transaction_category`, `option_type`
- `position_direction`, `options_position_status`, `leg_role`
- `equity_position_source`, `equity_position_status`

### Decimal Precision
| Field | Type | Rationale |
|---|---|---|
| `price`, `amount`, `commission`, `realized_pnl`, `equity_realized_pnl`, `cost_basis_per_share` | `Numeric(12, 4)` | 4dp handles fractional cent precision |
| `strike` | `Numeric(12, 4)` | 3dp in raw CSV; store 4dp for safety |
| `quantity` | `Numeric(15, 5)` | Fractional equity shares (D21) |

### Soft Delete Pattern
Models with `status` + `deleted_at`:
- `Upload`: `UploadStatus` (ACTIVE | SOFT_DELETED)
- `Transaction`: `TransactionStatus` (ACTIVE | SOFT_DELETED)
- `OptionsPosition`: uses `OptionsPositionStatus` (includes EXPIRED/ASSIGNED/EXERCISED); `deleted_at` for cascade soft-delete
- `EquityPosition`: `EquityPositionStatus` (OPEN | CLOSED); `deleted_at` for cascade

### Self-Referential FK
`OptionsPosition.parent_position_id → options_positions.id` is nullable and reserved for v1.0 roll-chain tracking. No cascade.

### JSONB
`RawTransaction.raw_data` stores the original CSV row as JSONB for full audit trail.

---

## Required Indexes (PRD §4)

```sql
-- Supports upload-scoped transaction queries + category/symbol filtering
CREATE INDEX ix_transactions_upload_symbol_category_date
    ON transactions (upload_id, symbol, category, transaction_date);

-- Supports position list queries filtered by underlying + status + expiry range
CREATE INDEX ix_options_positions_underlying_status_expiry
    ON options_positions (underlying, status, expiry);
```

Additional indexes added as FK backing indexes (PostgreSQL does not auto-create FK indexes):
- `raw_transactions.upload_id`
- `transactions.raw_transaction_id`, `transactions.upload_id`
- `options_position_legs.position_id`, `options_position_legs.transaction_id`
- `equity_positions.assigned_position_id`, `equity_positions.close_transaction_id`

---

## Migration Strategy

Since a live PostgreSQL instance is not available at migration-generation time, the migration is hand-written using Alembic op directives. The migration is a single revision (`initial_schema`) that creates all tables and indexes in FK-dependency order:

1. `uploads`
2. `raw_transactions` (FK → uploads)
3. `transactions` (FK → raw_transactions, uploads)
4. `options_positions` (self-referential FK added post-create)
5. `options_position_legs` (FK → options_positions, transactions)
6. `equity_positions` (FK → options_positions, transactions)

`downgrade()` drops in reverse order.

---

## Test Strategy

Unit tests in `tests/unit/test_models.py` achieve 100% branch coverage by:
- Importing all models (executes class bodies / column declarations)
- Asserting `__tablename__` values
- Asserting enum member names and values
- Instantiating each model with required fields and verifying defaults
- Verifying `Column.type` classes on key columns

No live DB required — all tests are pure Python import + attribute inspection.
