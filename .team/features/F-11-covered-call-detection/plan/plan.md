# F-11: Covered Call Detection — Implementation Plan

**Owner:** backend-tdd-api-dev  
**Date:** 2026-03-31  
**Status:** Approved  
**Depends on:** F-09 (Options Position Matcher), F-05 (Database Schema)

---

## Objective

Implement covered call detection logic that stamps `OptionsPosition.is_covered_call` at position-creation time and re-evaluates it after any upload that affects equity holdings for the same underlying. A short CALL is considered covered if the user holds at least 100 shares of the underlying per open contract at the time of evaluation.

---

## Files to Create / Modify

```
backend/app/services/
  covered_call.py                   ← new: detection + re-evaluation logic

backend/app/repositories/
  equity_position_repository.py     ← extend: share count query by symbol
  options_position_repository.py    ← extend: open short CALL query by underlying

backend/tests/unit/
  test_covered_call.py              ← new: full unit coverage with mocked DB

backend/tests/integration/
  test_covered_call_integration.py  ← new: round-trip against test DB
```

---

## Open Question Resolutions Affecting This Feature

None of the five open questions (OQ1–OQ5) directly alter covered call detection rules. OQ1 (equity P&L inclusion) is the reason `EquityPosition` records are available; this feature depends on that infrastructure but does not change OQ1 semantics.

---

## Design Decisions

### Definition of "Covered" (PRD §3.3.5)

A short CALL position is considered covered if:

```
sum of OPEN EquityPosition.quantity WHERE symbol == position.underlying
>= position.open_contract_count * 100
```

- `open_contract_count` = sum of quantities of all OPEN-role `OptionsPositionLeg` records on this position (net unmatched contracts remaining).
- Only `EquityPosition` records with `status = OPEN` count toward the share balance.
- `EquityPosition` records from all sources (`PURCHASE`, `ASSIGNMENT`, `EXERCISE`) are included in the share count — the source does not affect coverage eligibility.
- Only `OptionsPosition` records with `direction = SHORT` and `option_type = CALL` are eligible for covered-call stamping.

### Stamp at Creation Time (PRD §3.3.5, D5)

When the position matcher (F-09) creates a new `OptionsPosition` for a `SHORT CALL`, the covered call service is invoked immediately to compute and set `is_covered_call`. This happens within the same DB session/transaction as position creation so the stamp is atomic with the position record.

### Re-evaluation Triggers (PRD §3.3.5)

After any upload is processed, if the upload contains any of the following transaction categories:
- `EQUITY_BUY`
- `OPTIONS_ASSIGNED`
- `OPTIONS_EXERCISED`

...then `is_covered_call` must be re-evaluated for **all OPEN short CALL positions** in every underlying that appears in those transactions. This re-evaluation also fires when any of the above categories is present due to a **soft-delete cascade** (deleting an upload that had equity-creating transactions may reduce the share count below coverage threshold).

Re-evaluation does **not** trigger for:
- Close-only uploads (BTC, STC, expiry)
- Uploads containing only non-equity categories (dividends, fees, interest)

### Long CALL and PUT Positions

`is_covered_call` is always `False` for LONG positions and for PUT positions (regardless of direction). The service must guard against accidentally stamping non-CALL or non-SHORT positions.

### Cash-Secured Put — Not Covered

A cash-secured put is not a "covered" position in the covered-call sense. There is no `is_cash_secured` flag in v0.1 (deferred). The service only stamps `is_covered_call` and only for `SHORT CALL` positions.

### Service Interface

```python
async def stamp_covered_call(
    session: AsyncSession,
    position: OptionsPosition,
) -> None:
    """
    Evaluates and sets position.is_covered_call for a SHORT CALL position.
    Reads current OPEN EquityPosition share count for position.underlying.
    No-op if position is not SHORT CALL.
    """

async def re_evaluate_covered_calls(
    session: AsyncSession,
    affected_underlyings: set[str],
) -> int:
    """
    Re-evaluates is_covered_call for all OPEN SHORT CALL positions
    in the given underlyings. Returns count of positions re-evaluated.
    """
```

---

## Implementation Details

### `covered_call.py`

**`_is_short_call(position: OptionsPosition) -> bool`**

```python
def _is_short_call(position: OptionsPosition) -> bool:
    return (
        position.direction == PositionDirection.SHORT
        and position.option_type == OptionType.CALL
    )
```

**`_open_contract_count(position: OptionsPosition) -> Decimal`**

Sums `OptionsPositionLeg.quantity` for all legs with `leg_role = OPEN` on this position, minus sum of `CLOSE` legs. This is the number of remaining open contracts.

Alternatively: `total_open_qty - total_close_qty` where both are read from the position's legs via repository.

**`_get_share_balance(session, underlying) -> Decimal`**

Queries `EquityPosition` table:
```sql
SELECT COALESCE(SUM(quantity), 0)
FROM equity_positions
WHERE symbol = :underlying
  AND status = 'OPEN'
  AND deleted_at IS NULL
```

**`stamp_covered_call(session, position)`**

```python
async def stamp_covered_call(session, position):
    if not _is_short_call(position):
        position.is_covered_call = False
        return
    open_contracts = await get_open_contract_count(session, position.id)
    required_shares = open_contracts * 100
    actual_shares = await _get_share_balance(session, position.underlying)
    position.is_covered_call = (actual_shares >= required_shares)
```

**`re_evaluate_covered_calls(session, affected_underlyings)`**

```python
async def re_evaluate_covered_calls(session, affected_underlyings):
    positions = await find_open_short_call_positions(session, affected_underlyings)
    for position in positions:
        await stamp_covered_call(session, position)
    return len(positions)
```

### Repository Extensions

**`equity_position_repository.py`**

```python
async def get_open_share_balance(session, symbol: str) -> Decimal:
    """Sum of quantity across all OPEN EquityPosition records for symbol."""
```

**`options_position_repository.py`**

```python
async def find_open_short_call_positions(
    session, underlyings: set[str]
) -> list[OptionsPosition]:
    """
    Returns all OptionsPosition records where:
    - underlying IN :underlyings
    - direction = SHORT
    - option_type = CALL
    - status IN (OPEN, PARTIALLY_CLOSED)
    - deleted_at IS NULL
    """

async def get_open_contract_count(
    session, position_id: UUID
) -> Decimal:
    """
    Sum of OPEN leg quantities minus sum of CLOSE leg quantities
    for the given position_id.
    """
```

### Integration Into Upload Pipeline (F-12 calls this)

The upload orchestration in F-12 calls the covered call service at two points:

1. **At position creation (in F-09 matcher):** F-09 calls `stamp_covered_call(session, position)` immediately after creating each new `SHORT CALL` position.

2. **After full upload processing (in F-12 orchestrator):** After all transactions in the upload have been matched, F-12 checks if any `EQUITY_BUY`, `OPTIONS_ASSIGNED`, or `OPTIONS_EXERCISED` transactions were processed. If so, it collects the set of affected underlyings and calls `re_evaluate_covered_calls(session, affected_underlyings)`.

---

## Test Strategy

### Unit Tests (`tests/unit/test_covered_call.py`)

**`_is_short_call`:**

| Position type | Expected result |
|---|---|
| `direction=SHORT, option_type=CALL` | `True` |
| `direction=LONG, option_type=CALL` | `False` |
| `direction=SHORT, option_type=PUT` | `False` |
| `direction=LONG, option_type=PUT` | `False` |

**`stamp_covered_call` (mocked share balance and contract count):**

| Scenario | `open_contracts` | `share_balance` | Expected `is_covered_call` |
|---|---|---|---|
| 1 contract, 100 shares (exactly covered) | 1 | 100 | `True` |
| 1 contract, 101 shares (more than covered) | 1 | 101 | `True` |
| 1 contract, 99 shares (not covered) | 1 | 99 | `False` |
| 2 contracts, 200 shares | 2 | 200 | `True` |
| 2 contracts, 199 shares | 2 | 199 | `False` |
| 1 contract, 0 shares (naked) | 1 | 0 | `False` |
| Position is LONG CALL (guard) | — | — | `False` (no-op) |
| Position is SHORT PUT (guard) | — | — | `False` (no-op) |

**`re_evaluate_covered_calls`:**

| Scenario | Mock setup | Expected |
|---|---|---|
| Two SHORT CALL positions in same underlying, share balance drops | 2 positions; share balance reduces to below coverage | Both re-evaluated to `False` |
| No SHORT CALL positions in affected underlyings | `[]` from repository | Returns `0` |
| Empty `affected_underlyings` set | — | No repository call; returns `0` |
| Share balance increases above threshold | 1 position; balance goes from 0 to 100 | `is_covered_call` changes to `True` |

### Integration Tests (`tests/integration/test_covered_call_integration.py`)

| Scenario | Steps | Expected DB state |
|---|---|---|
| STO before equity purchase | STO CALL (1 contract); 0 shares held | `is_covered_call = False` |
| STO after equity purchase | Buy 100 shares; then STO CALL | `is_covered_call = True` (stamped at creation) |
| Buy equity, re-evaluate | STO CALL (naked); then EQUITY_BUY 100 shares; re-evaluate | `is_covered_call = True` |
| Sell equity, re-evaluate | Start: STO CALL + 100 shares; EQUITY_SELL 100 shares; re-evaluate | `is_covered_call = False` |
| Assignment creates equity, re-evaluate | STO CALL (uncovered); assignment closes PUT → 100 shares created; re-evaluate | `is_covered_call = True` if shares now ≥ threshold |
| Scale-in: 2 contracts, 100 shares | 2x STO CALL (scale-in); 100 shares | `is_covered_call = False` (need 200 shares) |
| Scale-in: 2 contracts, 200 shares | 2x STO CALL; 200 shares | `is_covered_call = True` |
| Soft-delete upload removes equity lot | Upload A: BTO 100 shares. STO CALL → covered. Delete upload A → 0 shares | `is_covered_call = False` after re-evaluation |
| Multiple underlyings | Re-evaluate called with `{AAPL, NVDA}` | Only AAPL and NVDA positions re-evaluated |

### Coverage Requirements

100% line and branch coverage on `covered_call.py` and all repository methods introduced by this feature. Every branch of the `>= required_shares` comparison, every guard clause, and the empty-set short-circuit must be covered.
