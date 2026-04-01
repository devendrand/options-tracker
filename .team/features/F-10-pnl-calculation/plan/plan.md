# F-10: P&L Calculation Service

**Feature:** F-10  
**Owner:** backend-tdd-api-dev  
**Status:** Pending plan  
**Depends on:** F-09 (Options Position Matcher)

---

## Open Question Resolutions Affecting This Feature

### OQ1 — Equity P&L in v0.1 (Resolved 2026-03-30)

**Resolution:** Include equity P&L calculation in v0.1 as a **Should Have** feature.

**Rationale summary:** The `EquityPosition` schema already supports it (`equity_realized_pnl`, `close_transaction_id`, `closed_at`). Equity lots are created from `EQUITY_BUY`, `OPTIONS_ASSIGNED`, and `OPTIONS_EXERCISED` — assignment/exercise lots are direct consequences of options activity. Leaving them untracked creates a blind spot for covered call and CSP users. Soft-delete cascade logic also requires consistent handling for both position types.

**Implementation requirements for `pnl.py`:**

1. **Options P&L** (existing requirement):
   - Formula: `Open Amount + Close Amount − |open_commission| − |close_commission|`
   - Amounts = `price × 100 × quantity` (cash-flow signed)
   - Partial close: P&L on closed FIFO-matched portion only

2. **Equity P&L** (added by OQ1):
   - Formula: `(sell_price − cost_basis_per_share) × quantity_sold`
   - `EQUITY_SELL` transactions close `EquityPosition` records (FIFO by `created_at` if multiple lots)
   - Sets `equity_realized_pnl` and `status = CLOSED` on matched lots
   - Partial sell: proportional cost basis applied; remaining lot stays `OPEN` with reduced quantity

3. **P&L aggregation** must cover both position types:
   - By position (options or equity)
   - By underlying symbol
   - By calendar month (of `transaction_date`)
   - By calendar year (of `transaction_date`)

**Test scenarios required:**
- Covered call (STO + BTC): options P&L correct
- Long call expiry worthless: close amount = $0.00
- Assignment: equity lot created; equity P&L on subsequent equity sell
- Partial options close: only closed portion contributes realized P&L
- `EQUITY_BUY` + `EQUITY_SELL` (full close): correct equity P&L
- `EQUITY_BUY` + partial `EQUITY_SELL`: remaining lot open, correct proportional P&L
- Multiple equity lots (FIFO): oldest lot closed first
- Cash-secured put assignment: equity lot at strike price as cost basis
