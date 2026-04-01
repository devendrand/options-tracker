# F-08: Deduplication Service — Implementation Plan

**Owner:** backend-tdd-api-dev  
**Date:** 2026-03-31  
**Status:** Approved  
**Depends on:** F-05 (Database Schema), F-06 (E*TRADE CSV Parser), F-07 (Transaction Classifier)

---

## Objective

Implement the `deduplicator.py` service that computes the Tier 2 composite deduplication key for each parsed E*TRADE transaction, queries the database for existing matches, and stamps each `RawTransaction` record with `ACTIVE`, `DUPLICATE`, or `POSSIBLE_DUPLICATE` status before any `Transaction` records are created.

---

## Files to Create / Modify

```
backend/app/services/
  deduplicator.py               ← new: deduplication logic

backend/app/repositories/
  raw_transaction_repository.py ← new (or extend existing): composite-key lookup query

backend/tests/unit/
  test_deduplicator.py          ← new: full unit coverage with mocked DB

backend/tests/integration/
  test_deduplicator_integration.py  ← new: round-trip against test DB
```

---

## Open Question Resolutions Affecting This Feature

None of the five open questions (OQ1–OQ5) directly affect deduplication logic. All deduplication rules are fully resolved via D2 and D16 in the PRD.

---

## Design Decisions

### Tier 2 Composite Key Only (D2, D16)

E*TRADE CSV exports contain no unique broker transaction ID field. The only applicable deduplication strategy is the Tier 2 composite key:

```
(trade_date, transaction_date, settlement_date, activity_type, description,
 symbol, quantity, price, amount, commission)
```

Tier 1 deduplication (broker transaction ID matching) does not apply to E*TRADE and must not be implemented in this service. The architecture should allow Tier 1 to be added per broker adapter in v0.2 without changing this service.

### Status Assignment Rules (PRD §3.1.3)

| Condition | Status assigned to incoming row |
|---|---|
| No existing `RawTransaction` matches the composite key | `ACTIVE` |
| Exactly one existing `ACTIVE` `RawTransaction` matches the composite key | `DUPLICATE` (first upload wins; incoming row is suppressed) |
| More than one existing `RawTransaction` matches the composite key, or a match exists that is itself `POSSIBLE_DUPLICATE` | `POSSIBLE_DUPLICATE` (surfaced for user review; not auto-suppressed) |

The definition of "collision" (POSSIBLE_DUPLICATE) is: the composite key matches an existing record but the confidence is not high enough to auto-suppress. In practice this is triggered when:
- A second matching row is found and there is already a `DUPLICATE` or `POSSIBLE_DUPLICATE` with that key, or
- The implementation team determines an ambiguous data condition exists.

For the MVP1 implementation, the rule is:
- **Zero matches** → `ACTIVE`
- **Exactly one ACTIVE match** → incoming row is `DUPLICATE`
- **Any other match condition** (match exists but is itself not `ACTIVE`, or multiple matches) → incoming row is `POSSIBLE_DUPLICATE`

### "First Upload Wins" Semantics

The existing record's status is never mutated by the deduplication service. Only the status of the incoming (new) `RawTransaction` is set. The earlier upload's record retains its `ACTIVE` status.

### Deduplication Runs Before Transaction Record Creation

The service is called after parsing and classification, but before `Transaction` records are written. Only `ACTIVE` `RawTransaction` records proceed to `Transaction` creation. `DUPLICATE` and `POSSIBLE_DUPLICATE` records are stored in `raw_transactions` but do not produce `Transaction` rows.

### Null Handling in Composite Key

`settlement_date`, `symbol`, `quantity`, `price`, and `amount` are all nullable. The SQL query must use `IS NOT DISTINCT FROM` (or equivalent ORM expression) for nullable columns so that two rows where `settlement_date IS NULL` match each other correctly. Standard `=` comparisons with `NULL` would never match.

### Service Interface

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from app.models.enums import RawTransactionStatus

@dataclass
class DeduplicationInput:
    trade_date: date
    transaction_date: date
    settlement_date: date | None
    activity_type: str
    description: str
    symbol: str | None
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal | None
    commission: Decimal

def determine_status(
    incoming: DeduplicationInput,
    existing_matches: list[RawTransactionStatus],
) -> RawTransactionStatus:
    """
    Pure function. Given the statuses of any existing RawTransaction records
    that share the composite key, return the appropriate status for the
    incoming record.
    """
    ...
```

The repository handles the DB lookup; `determine_status` is a pure function for easy unit testing.

---

## Implementation Details

### `deduplicator.py`

```
app/services/deduplicator.py
```

**`DeduplicationInput` dataclass**
- Fields exactly matching the composite key columns (types per schema: `date`, `str`, `Decimal | None`)
- No ORM dependencies — pure Python dataclass

**`determine_status(incoming, existing_matches) -> RawTransactionStatus`**
- `existing_matches`: list of `RawTransactionStatus` values from existing DB records sharing the composite key
- Logic:
  - `len(existing_matches) == 0` → `ACTIVE`
  - `len(existing_matches) == 1 and existing_matches[0] == ACTIVE` → `DUPLICATE`
  - All other cases → `POSSIBLE_DUPLICATE`

**`build_composite_key(parsed_tx: ParsedTransaction) -> DeduplicationInput`**
- Maps fields from `ParsedTransaction` (produced by F-06 parser) to `DeduplicationInput`
- `activity_type` = `parsed_tx.activity_type_raw` (raw CSV string, not internal category)
- `commission` is always present (defaults to `Decimal('0.00')` in parser)

### `raw_transaction_repository.py` — Composite Key Lookup

```python
async def find_by_composite_key(
    session: AsyncSession,
    key: DeduplicationInput,
) -> list[RawTransaction]:
    """
    Returns all existing RawTransaction records that share the composite key.
    Uses IS NOT DISTINCT FROM for nullable columns.
    Excludes SOFT_DELETED records (status != SOFT_DELETED).
    """
```

SQL condition pattern for nullable columns:
```sql
(settlement_date IS NOT DISTINCT FROM :settlement_date)
AND (symbol IS NOT DISTINCT FROM :symbol)
AND (quantity IS NOT DISTINCT FROM :quantity)
AND (price IS NOT DISTINCT FROM :price)
AND (amount IS NOT DISTINCT FROM :amount)
```

Non-nullable columns use standard equality:
```sql
trade_date = :trade_date
AND transaction_date = :transaction_date
AND activity_type = :activity_type
AND description = :description
AND commission = :commission
```

### Integration Into Upload Pipeline (F-12 will call this)

The upload orchestration in F-12 calls the deduplication service for each parsed row:

```
parse_csv → classify → for each ParsedTransaction:
    key = build_composite_key(parsed_tx)
    matches = await find_by_composite_key(session, key)
    status = determine_status(key, [m.status for m in matches])
    raw_tx = RawTransaction(..., status=status)
    session.add(raw_tx)
    if status == ACTIVE:
        tx = Transaction(...)
        session.add(tx)
```

The deduplication service itself is stateless and does not manage DB sessions.

---

## Test Strategy

All tests follow TDD (tests written before implementation). Unit tests use mocked DB; integration tests use the test DB.

### Unit Tests (`tests/unit/test_deduplicator.py`)

**`determine_status` — pure function, no DB needed:**

| Scenario | `existing_matches` input | Expected status |
|---|---|---|
| First upload, no existing records | `[]` | `ACTIVE` |
| Second upload, one ACTIVE match | `[ACTIVE]` | `DUPLICATE` |
| Third upload, match exists but is already DUPLICATE | `[DUPLICATE]` | `POSSIBLE_DUPLICATE` |
| Match exists but is POSSIBLE_DUPLICATE | `[POSSIBLE_DUPLICATE]` | `POSSIBLE_DUPLICATE` |
| Multiple matches (two ACTIVE) | `[ACTIVE, ACTIVE]` | `POSSIBLE_DUPLICATE` |
| Match exists and is PARSE_ERROR | `[PARSE_ERROR]` | `POSSIBLE_DUPLICATE` |

**`build_composite_key` — field mapping:**
- All fields populated → key matches source fields exactly
- `settlement_date = None` → key has `None`
- `symbol = None` (sentinel `--`) → key has `None`
- `quantity = None` → key has `None`
- `price = None` → key has `None`
- `amount = None` → key has `None`
- `commission` blank in CSV → key has `Decimal('0.00')`

### Integration Tests (`tests/integration/test_deduplicator_integration.py`)

Requires live test DB (pytest-asyncio + test database fixture).

| Scenario | Steps | Expected outcome |
|---|---|---|
| Fresh upload, unique row | Insert row A; lookup composite key | Returns `[]`; row A gets `ACTIVE` |
| Duplicate upload | Insert row A (ACTIVE); upload row A again; lookup | Returns `[ACTIVE]`; second row gets `DUPLICATE` |
| Collision — third upload | Row A (ACTIVE), row A copy (DUPLICATE) exist; upload row A again | Returns `[ACTIVE, DUPLICATE]`; third gets `POSSIBLE_DUPLICATE` |
| Nullable settlement_date match | Two rows, both with `settlement_date = NULL`, same other fields | Correctly identified as matching |
| Nullable settlement_date no-match | One row NULL, one row with date — different rows | Correctly identified as non-matching |
| Nullable symbol match | `symbol = NULL` on both rows | Correctly identified as matching |
| Decimal quantity precision | `quantity = Decimal('0.213')` (fractional share, D21) | Matches correctly |
| Soft-deleted records excluded | Row A (SOFT_DELETED); upload row A again | Returns `[]`; incoming gets `ACTIVE` |

### Coverage Requirements

100% line and branch coverage on `deduplicator.py` and the dedup-related repository method. All branches of `determine_status` must be explicitly covered. The nullable-column comparison branches must be tested with both `None` and non-`None` values.
