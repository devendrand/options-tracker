# F-05 Review — Database Schema + Alembic Migrations

**Reviewer:** tech-lead-architect
**Date:** 2026-03-31
**Verdict:** APPROVED

## Checklist

- [x] All enums match CLAUDE.md domain rules exactly
- [x] All columns have correct types, nullability, defaults per plan
- [x] Required indexes from PRD §4 present
- [x] Foreign keys and cascade rules correct
- [x] Migration creates/drops in correct FK dependency order
- [x] Migration enum values match Python enums exactly
- [x] Tests cover all models, enums, relationships, indexes, defaults
- [x] No missing columns or tables vs PRD requirements

## Findings

### Quality Gates

All four CI gates pass clean:

- `ruff check`: all checks passed
- `ruff format --check`: 33 files already formatted
- `mypy app`: success, no issues found in 21 source files
- `pytest --cov=app --cov-branch --cov-fail-under=100`: 240 tests passed, 100% line and branch coverage

### Enum Correctness

All 9 enum classes match the domain rules in CLAUDE.md exactly:

- `TransactionCategory` — all 7 options categories and 8 equity/other categories present, values match string literals verbatim.
- `OptionsPositionStatus` — all 6 states (OPEN, PARTIALLY_CLOSED, CLOSED, EXPIRED, ASSIGNED, EXERCISED) present.
- `RawTransactionStatus` — ACTIVE, DUPLICATE, POSSIBLE_DUPLICATE, PARSE_ERROR all present and correctly named.
- All other enums (`UploadStatus`, `TransactionStatus`, `OptionType`, `PositionDirection`, `LegRole`, `EquityPositionSource`, `EquityPositionStatus`) match specification.

### Schema Correctness

All models are well-formed:

- Decimal precision choices are appropriate: `Numeric(12, 4)` for monetary/price fields, `Numeric(15, 5)` for quantity to support fractional equity shares (D21).
- UUID primary keys with `uuid.uuid4` callables as column-level defaults — consistent across all 6 models.
- Soft-delete pattern (`status` + `deleted_at`) correctly applied to Upload, Transaction, OptionsPosition, and EquityPosition.
- `RawTransaction.raw_data` stored as JSONB with full audit trail intent.
- `OptionsPosition.parent_position_id` self-referential FK is nullable with `ondelete="SET NULL"` and correctly documented as reserved for v1.0 roll-chain tracking.
- `EquityPosition.assigned_position_id` and `close_transaction_id` are both nullable with `ondelete="SET NULL"`, correct for the assignment/exercise lifecycle.

### Required Indexes (PRD §4)

Both PRD-required composite indexes are present and have correct column order:

- `ix_transactions_upload_symbol_category_date` on `(upload_id, symbol, category, transaction_date)`
- `ix_options_positions_underlying_status_expiry` on `(underlying, status, expiry)`

All FK backing indexes are also present for every foreign key column, preventing sequential scans on FK lookups.

### Migration

The migration creates tables in correct FK dependency order (uploads → raw_transactions → transactions → options_positions → options_position_legs → equity_positions) and drops in strict reverse order. All 9 PostgreSQL ENUM types are created before any table that references them, and dropped after all tables in the downgrade path. `checkfirst=True` on ENUM creation is good defensive practice. Enum string values in the migration match the Python enum values exactly.

### Test Quality

The test file covers all models, all enum members with count assertions, instantiation paths (required fields, optional fields, nullable defaults), column type inspection, index existence and column composition, relationship attributes via SQLAlchemy's `inspect()`, `Base.metadata` registration, and `__init__.py` re-export completeness. The `test_no_import_side_effects` test for idempotent re-import is a commendable defensive addition.

One minor observation: `test_upload_status_direct_import_alias` uses the `UploadStatusDirect` alias to exercise the direct-import path from `enums.py`. This is a deliberate coverage technique to ensure the `from app.models.enums import UploadStatus as UploadStatusDirect` import line is executed; it is acceptable.

### No Gaps Found

No columns or tables are missing relative to PRD requirements. The `OptionsPositionLeg` join table correctly models the multi-leg / partial-close requirement from the domain rules rather than using single FK columns on `OptionsPosition`.

## Verdict

APPROVED. The schema implementation is complete, correct, and well-tested. All domain rules from CLAUDE.md are faithfully represented. All PRD §4 indexes are present. The migration is hand-written conservatively and is safe to run against a fresh database. Coverage is 100% line and branch. No issues to address before merging.
