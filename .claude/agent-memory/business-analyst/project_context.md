---
name: Project Context
description: Options Tracker — PRD status, resolved decisions, and remaining open questions as of 2026-03-30
type: project
---

PRD updated to v0.4 on 2026-03-30. v0.3 was based on analysis of the actual E*TRADE CSV export sample file (SamoleTxnHistory.csv, ~288 transaction rows). v0.4 corrects broker name from "Schwab" to "E*TRADE" throughout — all format spec content (columns, parsing rules, activity types) remains unchanged.

**Status:** In Review (pre-implementation). All major structural decisions resolved. Remaining open questions are lower-stakes (see PRD Section 11).

## Resolved Decisions (as of v0.4)

- **Broker format (D17):** E*TRADE CSV only for MVP1. Broker field NOT required in upload API.
- **Dedup key (D16):** No broker transaction ID in E*TRADE format. Composite key only: `(trade_date, transaction_date, settlement_date, activity_type, description, symbol, quantity, price, amount, commission)`.
- **Internal transfer filtering (D18):** Paired TRNSFR rows stored as RawTransaction but excluded from analytics.
- **Sold Short / Bought To Cover disambiguation (D19):** Description-field regex is authoritative.
- **Option Expired price (D20):** Blank Price field defaults to 0.00; not a parse error.
- **Fractional share quantities (D21):** Quantity stored as Decimal on Transaction; equity can be fractional; options quantities remain whole numbers.

## Remaining Open Questions (PRD Section 11)

1. Equity P&L in v0.1 — should EQUITY_SELL calculate realized P&L?
2. Partial close display in UI — per-leg-pair vs single row with drawer
3. P&L summary period granularity
4. DRIP dividend paired-row handling
5. `Bought To Open` / `Sold To Close` — confirm both activity type variants supported alongside `Sold Short` / `Bought To Cover`

**Why:** These questions are lower risk but should be resolved before UI design begins.
**How to apply:** Surface these at the start of UI/frontend work, not before backend data model work.
