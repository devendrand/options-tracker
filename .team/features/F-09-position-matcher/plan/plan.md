# F-09: Options Position Matcher — Implementation Plan

**Owner:** backend-tdd-api-dev  
**Date:** 2026-03-31  
**Status:** Approved  
**Depends on:** F-05 (Database Schema), F-07 (Transaction Classifier), F-08 (Deduplication Service)

---

## Objective

Implement the `matcher.py` service that groups classified `Transaction` records by contract identity, applies FIFO open/close matching, manages `OptionsPosition` and `OptionsPositionLeg` records, creates `EquityPosition` records for assignment and exercise events, and stamps position status and direction on each position record.

---

## Files to Create / Modify

```
backend/app/services/
  matcher.py                        ← new: FIFO matching logic

backend/app/repositories/
  options_position_repository.py    ← new (or extend): position + leg queries
  equity_position_repository.py     ← new (or extend): equity lot queries

backend/tests/unit/
  test_matcher.py                   ← new: full unit coverage with mocked DB

backend/tests/integration/
  test_matcher_integration.py       ← new: round-trip against test DB
```

---

## Open Question Resolutions Affecting This Feature

### OQ1 — Equity P&L in v0.1 (Resolved 2026-03-30)

Equity P&L calculation is included in v0.1 (Should Have). The matcher's responsibility here is to **create** `EquityPosition` records for `EQUITY_BUY`, `OPTIONS_ASSIGNED`, and `OPTIONS_EXERCISED` transactions, and to **close** `EquityPosition` records (reducing quantity, setting status) when `EQUITY_SELL` transactions are processed. The actual P&L arithmetic (formula application) belongs to F-10; the matcher sets up the lot structure that F-10 reads.

---

## Design Decisions

### Contract Identity Key (PRD §3.3.1)

A unique options contract is identified by the four-tuple:

```
(underlying_symbol, strike_price, expiry_date, option_type)
```

All four fields must match exactly. The matcher groups `Transaction` records by this key before applying FIFO logic. `symbol` on the `Transaction` record is the underlying (not the OCC option symbol); the full OCC symbol is stored separately.

### FIFO Matching Algorithm (PRD §3.3.3, D7)

- Open legs are sorted ascending by `transaction_date` (oldest first).
- Close legs are sorted ascending by `transaction_date` (earliest first).
- The oldest open leg is matched against the earliest close leg for the same contract key.
- **Partial close:** If close quantity < open quantity, the open leg is split into two `OptionsPositionLeg` records: one matched (quantity = close quantity) and one unmatched (quantity = remaining). A new `OptionsPosition` record is created for the unmatched remainder. The original position's status moves from `OPEN` to `PARTIALLY_CLOSED`.
- **Scale-in (multiple open legs):** Multiple open transactions for the same contract create multiple `OptionsPositionLeg` records with `leg_role = OPEN` on the same `OptionsPosition`.
- The `OptionsPositionLeg` join table (not single FKs) is the authoritative model for all open/close leg relationships (D6).

### Position Status Rules (PRD §3.3.2)

| Condition | `OptionsPosition.status` |
|---|---|
| Total open quantity > total close quantity | `OPEN` |
| Total close quantity > 0 and < total open quantity | `PARTIALLY_CLOSED` |
| Total close quantity == total open quantity (standard close) | `CLOSED` |
| Close leg is `OPTIONS_EXPIRED` | `EXPIRED` |
| Close leg is `OPTIONS_ASSIGNED` | `ASSIGNED` |
| Close leg is `OPTIONS_EXERCISED` | `EXERCISED` |

`EXPIRED`, `ASSIGNED`, and `EXERCISED` are terminal statuses that also imply full closure. They take precedence over `CLOSED`.

### Position Direction (D8, PRD §5.5)

| Open Leg Category | `OptionsPosition.direction` |
|---|---|
| `OPTIONS_SELL_TO_OPEN` | `SHORT` |
| `OPTIONS_BUY_TO_OPEN` | `LONG` |

Direction is set at position-creation time from the first open leg. Scale-in legs must have the same direction; mismatched directions within the same contract key indicate a data error.

### Open Leg Categories (PRD §3.3.2)

Categories that produce an `OPEN` leg:
- `OPTIONS_BUY_TO_OPEN`
- `OPTIONS_SELL_TO_OPEN`

Categories that produce a `CLOSE` leg:
- `OPTIONS_BUY_TO_CLOSE`
- `OPTIONS_SELL_TO_CLOSE`
- `OPTIONS_EXPIRED`
- `OPTIONS_ASSIGNED`
- `OPTIONS_EXERCISED`

Non-options categories (`EQUITY_BUY`, `EQUITY_SELL`, `DIVIDEND`, etc.) do not create options positions. `EQUITY_BUY` and assignment/exercise events do create `EquityPosition` records.

### Assignment and Exercise — Separate Equity Lots (PRD §3.3.4, D4)

When a close leg category is `OPTIONS_ASSIGNED` or `OPTIONS_EXERCISED`:
1. The `OptionsPosition` is closed with status `ASSIGNED` or `EXERCISED`.
2. A **new** `EquityPosition` record is created:
   - `source = ASSIGNMENT` or `EXERCISE`
   - `cost_basis_per_share = strike_price` (from the options contract key)
   - `quantity` = contract quantity × 100 (shares per contract)
   - `assigned_position_id` = the closed `OptionsPosition.id`
   - `status = OPEN`
3. This lot is **never merged** with any existing `EquityPosition` for the same symbol. Each assignment/exercise event always creates a distinct lot.

### Equity Position Creation for EQUITY_BUY (PRD §3.4, D9)

Every `EQUITY_BUY` transaction produces a new `EquityPosition` record:
- `source = PURCHASE`
- `cost_basis_per_share = transaction.price`
- `quantity = transaction.quantity`
- `assigned_position_id = None`
- `status = OPEN`

### Equity Position Closure for EQUITY_SELL (PRD §3.4, OQ1)

When an `EQUITY_SELL` transaction is processed:
1. Find all `OPEN` `EquityPosition` records for the same symbol, ordered by `created_at` ascending (FIFO).
2. Deduct the sold quantity from the oldest open lot first.
3. If a lot's quantity reaches zero: set `status = CLOSED`, `closed_at = now()`, `close_transaction_id = transaction.id`. P&L is calculated in F-10, not here.
4. If sold quantity spans multiple lots (partial sell then full sell of next lot), process sequentially.
5. If sold quantity exceeds available open lots, this is a data error — flag the transaction with `status = PARSE_ERROR` (oversell not supported in v0.1; short equity is not tracked).

### Rolling Positions (PRD §3.3.6)

A roll is represented as two independent positions. The matcher does not detect or link rolls. `parent_position_id` remains `None` in v0.1.

### Multi-Leg Strategies (PRD §3.3.7)

Each leg is matched independently. No strategy-level grouping is performed.

### Idempotency Within an Upload

The matcher processes one upload at a time. All `Transaction` records from the current upload with `status = ACTIVE` are passed to the matcher. Previously processed transactions (from earlier uploads) are already persisted as `OptionsPosition` and `OptionsPositionLeg` records and must be accounted for when matching new close legs against existing open positions.

---

## Implementation Details

### `matcher.py` — Public Interface

```python
async def match_transactions(
    session: AsyncSession,
    transactions: list[Transaction],
) -> MatchResult:
    """
    Processes a batch of ACTIVE Transaction records (from one upload).
    Creates / updates OptionsPosition, OptionsPositionLeg, and EquityPosition records.
    Returns a MatchResult summary for upload post-processing.
    """

@dataclass
class MatchResult:
    positions_opened: int
    positions_closed: int
    positions_partially_closed: int
    equity_lots_created: int
    equity_lots_closed: int
```

### Matching Algorithm — Step by Step

**Step 1 — Separate transactions by role**

- Collect all `OPTIONS_*` transactions.
- Separate into opens and closes by category.
- Collect `EQUITY_BUY`, `EQUITY_SELL`, `OPTIONS_ASSIGNED`, `OPTIONS_EXERCISED` for equity processing.
- Ignore all other categories (`DIVIDEND`, `TRANSFER`, `INTEREST`, `FEE`, `JOURNAL`, `OTHER`).

**Step 2 — Process open legs**

For each open-category transaction (sorted ascending by `transaction_date`):
1. Build the contract key `(underlying, strike, expiry, option_type)`.
2. Query for an existing `OPEN` `OptionsPosition` with this contract key (same direction).
3. If found: add a new `OptionsPositionLeg(leg_role=OPEN, quantity=tx.quantity)` to that position. This is the scale-in path.
4. If not found: create a new `OptionsPosition` with `status=OPEN`, `direction` derived from category, and the first `OptionsPositionLeg(leg_role=OPEN)`.

**Step 3 — Process close legs**

For each close-category transaction (sorted ascending by `transaction_date`):
1. Build the contract key.
2. Query for existing `OPEN` or `PARTIALLY_CLOSED` `OptionsPosition` records with this contract key (opposite direction to the close type).
3. Apply FIFO across open legs (oldest `OptionsPositionLeg` with `leg_role=OPEN` and unmatched quantity first).
4. Deduct the close quantity from open legs sequentially.
5. If close quantity fully exhausts one or more open legs: set terminal status (`CLOSED`, `EXPIRED`, `ASSIGNED`, `EXERCISED`).
6. If close quantity partially exhausts the current open leg: split the leg — matched portion creates `OptionsPositionLeg(leg_role=CLOSE)`, unmatched remainder stays open.
7. Create `OptionsPositionLeg(leg_role=CLOSE, quantity=matched_quantity)`.
8. If `OPTIONS_ASSIGNED` or `OPTIONS_EXERCISED`: create `EquityPosition` (see above).

**Step 4 — Process equity transactions**

For each `EQUITY_BUY` transaction: create `EquityPosition(source=PURCHASE, ...)`.
For each `EQUITY_SELL` transaction: apply FIFO equity lot closure (see above).
For `OPTIONS_ASSIGNED` / `OPTIONS_EXERCISED`: already handled in Step 3; do not double-process.

**Step 5 — Recalculate position status**

After all legs are processed, recompute and persist `OptionsPosition.status` for all affected positions:
- Sum open leg quantities vs sum close leg quantities.
- Apply status rules from the table above.

### Repository Queries Required

```python
# options_position_repository.py
async def find_open_position_by_contract(
    session, underlying, strike, expiry, option_type, direction
) -> OptionsPosition | None

async def find_open_positions_by_contract(
    session, underlying, strike, expiry, option_type
) -> list[OptionsPosition]

async def get_open_legs_fifo(
    session, position_id
) -> list[OptionsPositionLeg]  # ordered by transaction.transaction_date ASC

# equity_position_repository.py
async def find_open_equity_lots_fifo(
    session, symbol
) -> list[EquityPosition]  # ordered by created_at ASC
```

---

## Test Strategy

### Unit Tests (`tests/unit/test_matcher.py`)

All unit tests mock the repository layer. Tests are pure logic tests against the matching algorithm.

**Open leg scenarios:**

| Scenario | Input | Expected outcome |
|---|---|---|
| Single STO — new position | 1x `OPTIONS_SELL_TO_OPEN`, no existing position | New `OptionsPosition(status=OPEN, direction=SHORT)`, 1x OPEN leg |
| Single BTO — new position | 1x `OPTIONS_BUY_TO_OPEN`, no existing position | New `OptionsPosition(status=OPEN, direction=LONG)`, 1x OPEN leg |
| Scale-in (two STO, same contract) | 2x `OPTIONS_SELL_TO_OPEN` | 1 position, 2x OPEN legs |
| Scale-in (existing open position) | 1x new STO, 1x existing OPEN position | Existing position gets second OPEN leg |

**Close leg scenarios:**

| Scenario | Expected outcome |
|---|---|
| Full BTC matching STO | `OptionsPosition.status = CLOSED` |
| Full STC matching BTO | `OptionsPosition.status = CLOSED` |
| Partial BTC (close qty < open qty) | `PARTIALLY_CLOSED`; remaining open quantity preserved |
| Expired option (OPTIONS_EXPIRED) | `status = EXPIRED`; close leg with quantity and price $0.00 |
| Assignment (OPTIONS_ASSIGNED) | `status = ASSIGNED`; new `EquityPosition(source=ASSIGNMENT)` created with `cost_basis = strike` |
| Exercise (OPTIONS_EXERCISED) | `status = EXERCISED`; new `EquityPosition(source=EXERCISE)` created with `cost_basis = strike` |
| Close with no matching open | Log warning; do not create position; do not raise (graceful degradation) |
| FIFO order: two open legs, one close | Oldest open leg reduced first |

**Equity scenarios:**

| Scenario | Expected outcome |
|---|---|
| `EQUITY_BUY` | New `EquityPosition(source=PURCHASE, status=OPEN)` |
| `EQUITY_SELL` full close | Oldest open lot: `status=CLOSED`, `close_transaction_id` set |
| `EQUITY_SELL` partial (spans two lots) | Oldest lot fully closed; second lot partially reduced |
| `EQUITY_SELL` exceeds available lots | Transaction flagged; no crash |
| Assignment lot never merged with PURCHASE lot | Two separate `EquityPosition` records for same symbol |

**Direction derivation:**

| Scenario | Expected direction |
|---|---|
| `OPTIONS_SELL_TO_OPEN` | `SHORT` |
| `OPTIONS_BUY_TO_OPEN` | `LONG` |

**Ignored categories:**

| Scenario | Expected outcome |
|---|---|
| `DIVIDEND` transaction passed to matcher | No position records created; no error |
| `TRANSFER` transaction passed to matcher | No position records created; no error |
| `FEE` transaction passed to matcher | No position records created; no error |

**Status computation:**

| Total open qty | Total close qty | Expected status |
|---|---|---|
| 2 | 0 | `OPEN` |
| 2 | 1 | `PARTIALLY_CLOSED` |
| 2 | 2 | `CLOSED` |
| 1 | 1 (EXPIRED) | `EXPIRED` |
| 1 | 1 (ASSIGNED) | `ASSIGNED` |
| 1 | 1 (EXERCISED) | `EXERCISED` |

### Integration Tests (`tests/integration/test_matcher_integration.py`)

Full round-trip against test DB. Use factory-boy for `Transaction` and `Upload` fixtures.

| Scenario | Steps | Expected DB state |
|---|---|---|
| Full covered call lifecycle | STO upload → BTC upload | `OptionsPosition.status = CLOSED`, 1 OPEN leg, 1 CLOSE leg |
| Partial close (scale-in) | 2x STO → 1x BTC | `PARTIALLY_CLOSED`; 2 OPEN legs; 1 CLOSE leg |
| Worthless expiry | BTO → EXPIRED | `status = EXPIRED`; P&L basis correct ($0 close) |
| Assignment | STO → ASSIGNED | `status = ASSIGNED`; new `EquityPosition` with `source=ASSIGNMENT` |
| Equity purchase and sale | `EQUITY_BUY` → `EQUITY_SELL` | `EquityPosition` moves to CLOSED |
| Cross-upload FIFO | Open from upload 1, close from upload 2 | Correct FIFO matching across uploads |
| Idempotent re-run (same upload twice) | Upload 1 processed; upload 1 re-submitted (dedup marks as DUPLICATE) | No duplicate positions created |

### Coverage Requirements

100% line and branch coverage on `matcher.py` and all new repository methods. Every status transition path must be covered by at least one test. All equity branches (PURCHASE / ASSIGNMENT / EXERCISE creation, FIFO sell closure, oversell guard) must be independently tested.
