# F-05 Database Schema — DB Dev Review

**Date:** 2026-03-31
**Reviewer:** postgres-alembic-dev agent
**Files reviewed:**
- `backend/app/models/enums.py`
- `backend/app/models/upload.py`
- `backend/app/models/raw_transaction.py`
- `backend/app/models/transaction.py`
- `backend/app/models/options_position.py`
- `backend/app/models/options_position_leg.py`
- `backend/app/models/equity_position.py`
- `backend/app/models/__init__.py`
- `backend/alembic/versions/20260330_a1b2c3d4e5f6_initial_schema.py`
- `backend/alembic/env.py`

---

## Schema Completeness

### Tables Present

All tables required by the PRD are present:

| Table | Status |
|---|---|
| `uploads` | Present |
| `raw_transactions` | Present |
| `transactions` | Present |
| `options_positions` | Present |
| `options_position_legs` | Present |
| `equity_positions` | Present |

### Enum Coverage

All 10 enum types are defined in `enums.py` and created before their dependent tables in the migration. All values match CLAUDE.md domain rules exactly.

| Enum | Status |
|---|---|
| `upload_status` | Correct |
| `raw_transaction_status` | Correct — includes ACTIVE, DUPLICATE, POSSIBLE_DUPLICATE, PARSE_ERROR |
| `transaction_status` | Correct |
| `transaction_category` | Correct — all 14 values match CLAUDE.md |
| `option_type` | Correct |
| `position_direction` | Correct |
| `options_position_status` | Correct — includes PARTIALLY_CLOSED, ASSIGNED, EXERCISED |
| `leg_role` | Correct |
| `equity_position_source` | Correct |
| `equity_position_status` | Correct |

### Column Types and Precision

**Numeric precision:**
- `price`, `strike`, `commission`, `amount`, `cost_basis_per_share`, `realized_pnl`: `Numeric(12, 4)` — supports values up to $99,999,999.9999 with 4 decimal places. Adequate for retail options pricing.
- `quantity` on `transactions` and `options_position_legs`: `Numeric(15, 5)` — correct per CLAUDE.md D21, supports fractional equity shares.

**String lengths:**
- `symbol`: `String(20)` — adequate for underlying tickers.
- `option_symbol`: `String(50)` — adequate for OCC-style option symbols (e.g., `AAPL  260117C00150000`).
- `broker_name`, `broker`: `String(50)` — adequate.
- `action`: `String(50)` — stores raw activity type from CSV (e.g., "Sold Short", "Bought To Cover"). Adequate.
- `broker_transaction_id`: `String(100)` — adequate.
- `filename`: `String(255)` — adequate for uploaded filenames.

**Date/time types:**
- Trade, transaction, settlement, expiry dates: `Date` — correct, no time component needed.
- `uploaded_at`, `deleted_at`, `closed_at`: `DateTime(timezone=True)` — correct, timezone-aware timestamps.

**No issues found** with column types.

### Deduplication Composite Key Fields on `transactions`

CLAUDE.md specifies a 10-field composite dedup key:
`(trade_date, transaction_date, settlement_date, activity_type, description, symbol, quantity, price, amount, commission)`

Mapping to the `transactions` table:

| Dedup Key Field | Column on `transactions` | Present? |
|---|---|---|
| `trade_date` | `trade_date` | Yes |
| `transaction_date` | `transaction_date` | Yes |
| `settlement_date` | `settlement_date` (nullable) | Yes |
| `activity_type` | `action` | Yes — stored as raw activity type |
| `description` | **MISSING** | **NO** |
| `symbol` | `symbol` | Yes |
| `quantity` | `quantity` | Yes |
| `price` | `price` (nullable) | Yes |
| `amount` | `amount` | Yes |
| `commission` | `commission` | Yes |

**ISSUE — Missing `description` column:** The `description` field from the E*TRADE CSV is required in the dedup composite key (per CLAUDE.md) but is absent from both the `Transaction` ORM model and the migration. This is not merely a convenience field — without it:
1. Deduplication cannot be implemented as specified.
2. Disambiguation of `Sold Short` / `Bought To Cover` (options vs equity) requires the description at classification time. The classifier currently has access to description only via the `raw_data` JSONB on `RawTransaction`, which requires a join and JSON extraction — this is workable but suboptimal.
3. The dedup tier-2 "collision" check (same `trade_date + symbol + quantity + amount`) is implementable without it, but the tier-1 exact-match check cannot be complete.

A new migration to add `description TEXT` to `transactions` is needed before F-08 work begins. See "Recommended Schema Changes" below.

### FK Cascade Rules

| FK | Rule | Correct? |
|---|---|---|
| `raw_transactions.upload_id` → `uploads.id` | CASCADE | Yes — raw rows should be deleted with their upload |
| `transactions.raw_transaction_id` → `raw_transactions.id` | CASCADE | Yes |
| `transactions.upload_id` → `uploads.id` | CASCADE | Yes |
| `options_position_legs.position_id` → `options_positions.id` | CASCADE | Yes — legs are meaningless without their position |
| `options_position_legs.transaction_id` → `transactions.id` | CASCADE | Yes |
| `options_positions.parent_position_id` → `options_positions.id` | SET NULL | Yes — self-referential; child survives parent deletion |
| `equity_positions.assigned_position_id` → `options_positions.id` | SET NULL | Yes — equity lot persists if options position is deleted |
| `equity_positions.close_transaction_id` → `transactions.id` | SET NULL | Yes — equity lot persists with null close FK if transaction deleted |

All cascade rules match domain requirements. No issues.

### Indexes

**Present indexes:**

| Index | Columns | Type | Correct? |
|---|---|---|---|
| `ix_raw_transactions_upload_id` | `upload_id` | B-tree | Yes |
| `ix_transactions_raw_transaction_id` | `raw_transaction_id` | B-tree | Yes |
| `ix_transactions_upload_id` | `upload_id` | B-tree | Yes |
| `ix_transactions_upload_symbol_category_date` | `upload_id, symbol, category, transaction_date` | B-tree | Yes — PRD §4 |
| `ix_options_positions_parent_position_id` | `parent_position_id` | B-tree | Yes |
| `ix_options_positions_underlying_status_expiry` | `underlying, status, expiry` | B-tree | Yes — PRD §4 |
| `ix_options_position_legs_position_id` | `position_id` | B-tree | Yes |
| `ix_options_position_legs_transaction_id` | `transaction_id` | B-tree | Yes |
| `ix_equity_positions_assigned_position_id` | `assigned_position_id` | B-tree | Yes |
| `ix_equity_positions_close_transaction_id` | `close_transaction_id` | B-tree | Yes |

**Missing indexes** (needed for F-08 deduplication and F-13 API queries — see Recommended Changes):
- No index on `equity_positions.symbol` — covered-call re-evaluation scans by symbol.
- No deduplication index on `transactions` for the exact-match and collision checks.

### Alembic env.py Configuration

The async setup is correct:
- Uses `async_engine_from_config` with `NullPool` — required to prevent connection pool persistence across migration runs.
- `do_run_migrations` uses `connection.run_sync()` — the standard pattern for running synchronous Alembic context inside an async connection.
- `DATABASE_URL` is read from the environment, not hardcoded — correct for multi-environment deployments.
- `target_metadata = Base.metadata` is set, enabling autogenerate diffs.
- `from app.models import *` ensures all ORM models are registered on `Base.metadata` before autogenerate runs.

No issues found.

### Migration Upgrade/Downgrade Symmetry

**Upgrade creates:**
10 enum types + 6 tables + 10 indexes

**Downgrade drops:**
6 tables (in correct reverse FK dependency order: equity_positions → options_position_legs → options_positions → transactions → raw_transactions → uploads) + 10 enum types

All indexes are dropped implicitly as part of their parent table drops — this is correct PostgreSQL behavior for non-partial, non-expression indexes attached to a table.

**Note on enum drop order in downgrade:** The downgrade drops enums in a defined order using `DROP TYPE IF EXISTS`. This is safe because all tables referencing the enums are dropped first, so no dependency violations occur. The order within enum drops is arbitrary but using `IF EXISTS` makes it idempotent.

The migration is **symmetric**. No issues.

---

## Deduplication Query Design

### Context

The deduplication service (F-08) operates during upload processing. For each incoming row, it must:

1. **Tier 1 — Exact match:** All 10 dedup key fields match → mark as `DUPLICATE`.
2. **Tier 2 — Collision:** `trade_date + symbol + quantity + amount` match but not all 10 fields → mark as `POSSIBLE_DUPLICATE`.

The service processes an entire upload batch at once, not row-by-row, so a bulk set-based approach is strongly preferred over per-row queries.

### Handling NULL in `settlement_date`

`settlement_date` is nullable. In SQL, `NULL = NULL` evaluates to `NULL` (unknown), not `TRUE`. For the composite key comparison to treat two NULLs as matching (which is correct here — two rows with no settlement date should be considered equal on this field), the comparison must use `IS NOT DISTINCT FROM` rather than `=`.

```sql
-- Correct NULL-safe equality:
t.settlement_date IS NOT DISTINCT FROM incoming.settlement_date

-- Wrong: NULL rows will never match:
t.settlement_date = incoming.settlement_date
```

The same applies to `price` (nullable) and any future nullable dedup key fields. The ORM layer (SQLAlchemy) does not apply `IS NOT DISTINCT FROM` automatically — this must be constructed explicitly.

### Recommended Query Pattern: Single Bulk Query with Lateral Join

Rather than issuing one query per incoming row, process the entire upload batch in a single query. This is critical for performance — a typical E*TRADE CSV export can have hundreds to thousands of rows.

**Step 1: Load the incoming batch into a temporary table or VALUES clause.**

For moderate-sized batches (< ~5000 rows), a `VALUES` clause works. For larger batches, use a temporary table.

```sql
-- Create temp table for incoming rows (populated before dedup query)
CREATE TEMP TABLE incoming_rows (
    import_row_num  INT,           -- client-side row index for correlation
    trade_date      DATE,
    transaction_date DATE,
    settlement_date DATE,          -- nullable
    action          TEXT,          -- activity_type
    description     TEXT,
    symbol          TEXT,
    quantity        NUMERIC(15, 5),
    price           NUMERIC(12, 4), -- nullable
    amount          NUMERIC(12, 4),
    commission      NUMERIC(12, 4)
) ON COMMIT DROP;
```

**Step 2: Single dedup classification query using LEFT JOINs.**

```sql
-- Returns one row per incoming row with its dedup classification.
-- Tier 1 (exact match on all 10 fields) takes priority over Tier 2.
SELECT
    ir.import_row_num,
    CASE
        WHEN exact.id IS NOT NULL     THEN 'DUPLICATE'
        WHEN collision.id IS NOT NULL THEN 'POSSIBLE_DUPLICATE'
        ELSE                               'ACTIVE'
    END AS dedup_status,
    exact.id     AS matched_transaction_id,
    collision.id AS collision_transaction_id
FROM incoming_rows ir

-- Tier 1: exact match on all 10 dedup key fields
LEFT JOIN LATERAL (
    SELECT t.id
    FROM transactions t
    WHERE t.status != 'SOFT_DELETED'
      AND t.trade_date        = ir.trade_date
      AND t.transaction_date  = ir.transaction_date
      AND t.settlement_date   IS NOT DISTINCT FROM ir.settlement_date
      AND t.action            = ir.action
      AND t.description       = ir.description          -- requires new column
      AND t.symbol            = ir.symbol
      AND t.quantity          = ir.quantity
      AND t.price             IS NOT DISTINCT FROM ir.price
      AND t.amount            = ir.amount
      AND t.commission        = ir.commission
    LIMIT 1
) exact ON true

-- Tier 2: collision check (same trade_date + symbol + quantity + amount,
--          but not all 10 fields — i.e., no exact match found)
LEFT JOIN LATERAL (
    SELECT t.id
    FROM transactions t
    WHERE exact.id IS NULL            -- only run if no exact match
      AND t.status != 'SOFT_DELETED'
      AND t.trade_date = ir.trade_date
      AND t.symbol     = ir.symbol
      AND t.quantity   = ir.quantity
      AND t.amount     = ir.amount
    LIMIT 1
) collision ON true;
```

The `LATERAL` subqueries short-circuit: Tier 2 only executes when Tier 1 found no match. This avoids unnecessary work. The `LIMIT 1` prevents multiple matches from multiplying output rows.

**SQLAlchemy async equivalent (conceptual — service layer implementation):**

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def classify_dedup_batch(
    session: AsyncSession,
    rows: list[dict],  # parsed transaction dicts
) -> list[str]:  # returns dedup_status per row
    # 1. Build a VALUES clause from the batch
    values_rows = ", ".join(
        f"({i}, :trade_date_{i}, :txn_date_{i}, :settle_{i}, "
        f":action_{i}, :description_{i}, :symbol_{i}, "
        f":qty_{i}, :price_{i}, :amount_{i}, :commission_{i})"
        for i in range(len(rows))
    )
    params = {}
    for i, row in enumerate(rows):
        params[f"trade_date_{i}"]  = row["trade_date"]
        params[f"txn_date_{i}"]    = row["transaction_date"]
        params[f"settle_{i}"]      = row.get("settlement_date")
        params[f"action_{i}"]      = row["action"]
        params[f"description_{i}"] = row.get("description")
        params[f"symbol_{i}"]      = row["symbol"]
        params[f"qty_{i}"]         = row["quantity"]
        params[f"price_{i}"]       = row.get("price")
        params[f"amount_{i}"]      = row["amount"]
        params[f"commission_{i}"]  = row["commission"]

    # 2. Execute via raw SQL (cleaner than constructing this with ORM)
    result = await session.execute(
        text(DEDUP_QUERY_TEMPLATE.format(values=values_rows)),
        params,
    )
    # 3. Map back to original row order by import_row_num
    statuses = ["ACTIVE"] * len(rows)
    for row in result:
        statuses[row.import_row_num] = row.dedup_status
    return statuses
```

Using `op.execute()` / `text()` for this query is intentional — the ORM cannot express `IS NOT DISTINCT FROM` or `LATERAL` joins cleanly, and the performance of a hand-written bulk query is significantly better than N per-row ORM queries.

### Hash Column Consideration

A SHA-256 hash of the 10 concatenated dedup key fields would simplify exact-match queries to a single indexed equality check (`dedup_hash = :hash`). However, for v0.1 scale (single user, hundreds of rows per upload), the complexity of maintaining a hash column does not justify the benefit.

Recommendation: **Defer the hash column.** Add a composite index on the high-cardinality subset of the dedup key instead (see below). Revisit hash if dedup performance becomes measurable.

---

## Recommended Schema Changes

The following changes are needed before F-08 (deduplication) and F-13 (transactions API) work begins. They should be implemented as a new migration, not by modifying the initial migration.

### Change 1 (Required for F-08): Add `description` column to `transactions`

The `description` field is part of the 10-field dedup composite key in CLAUDE.md. It is also used for disambiguation of `Sold Short` / `Bought To Cover` at classification time. Currently, the classifier must reach back to `raw_data` JSONB via a join.

```python
# New migration (F-08 prerequisite)
def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,   # nullable to avoid a NOT NULL violation on existing rows
        ),
    )

def downgrade() -> None:
    op.drop_column("transactions", "description")
```

Adding as `nullable=True` is the safe, zero-downtime pattern — no `server_default` is needed here since the column will be populated at parse time for all new rows. Existing rows (if any exist in staging/prod) will have NULL, which is acceptable since dedup only applies to future uploads.

### Change 2 (Required for F-08): Add deduplication index on `transactions`

Once `description` is added, a partial composite index on the four Tier 2 collision fields enables efficient collision detection. The Tier 1 exact-match check benefits from the same index as a leading prefix.

```python
# In the same migration as Change 1, or a separate one
def upgrade() -> None:
    # Supports both Tier 2 collision queries and prefix scans for Tier 1.
    # Use CREATE INDEX CONCURRENTLY to avoid table lock in production.
    op.create_index(
        "ix_transactions_dedup_collision",
        "transactions",
        ["trade_date", "symbol", "quantity", "amount"],
        postgresql_where=sa.text("status != 'SOFT_DELETED'"),
    )

def downgrade() -> None:
    op.drop_index("ix_transactions_dedup_collision", table_name="transactions")
```

`CREATE INDEX CONCURRENTLY` note: Alembic's `op.create_index` does not use `CONCURRENTLY` by default. For production deployments, the migration should be run manually using `CREATE INDEX CONCURRENTLY` or by passing `postgresql_concurrently=True` to `op.create_index`. This avoids a full table lock on `transactions` during the index build.

### Change 3 (Recommended for F-13 API): Add index on `equity_positions.symbol`

The covered-call re-evaluation logic (CLAUDE.md) scans equity positions by symbol after uploads containing `EQUITY_BUY`, `OPTIONS_ASSIGNED`, or `OPTIONS_EXERCISED`. Without an index, this is a sequential scan.

```python
def upgrade() -> None:
    op.create_index(
        "ix_equity_positions_symbol",
        "equity_positions",
        ["symbol"],
    )

def downgrade() -> None:
    op.drop_index("ix_equity_positions_symbol", table_name="equity_positions")
```

### Summary of Changes

| # | Table | Change | Priority |
|---|---|---|---|
| 1 | `transactions` | Add `description TEXT` column (nullable) | Required before F-08 |
| 2 | `transactions` | Add partial index on `(trade_date, symbol, quantity, amount)` where `status != 'SOFT_DELETED'` | Required before F-08 |
| 3 | `equity_positions` | Add index on `symbol` | Recommended before F-13 |

These should be delivered as a single new migration file (e.g., `20260401_XXXXXXXX_add_description_and_dedup_indexes.py`) after F-05 is merged, with both `upgrade()` and `downgrade()` functions.
