# F-07: Transaction Classifier

**Feature:** F-07  
**Owner:** backend-tdd-api-dev  
**Status:** Pending plan  
**Depends on:** F-06 (E*TRADE CSV Parser)

---

## Open Question Resolutions Affecting This Feature

### OQ4 — DRIP Dividend Handling (Resolved 2026-03-30)

**Resolution:** No special classifier logic required for DRIP transactions.

Both DRIP rows classify via the standard `Activity Type = Dividend` → `DIVIDEND` mapping. The classifier does NOT need DRIP-specific branches, pattern matching, or paired-row detection.

**Implementation notes:**
- `Activity Type: Dividend` always maps to `TransactionCategory.DIVIDEND` regardless of amount sign
- No `EquityPosition` is created from `DIVIDEND` transactions in v0.1
- DRIP pairing and equity lot creation from reinvestment purchases is explicitly deferred to v1.0

---

### OQ5 — `Bought To Open` / `Sold To Close` Activity Type Support (Resolved 2026-03-30)

**Resolution:** Both E*TRADE activity type variants are confirmed required. The classifier mapping table must include all variants.

**Complete mapping for affected activity types:**

| Activity Type | Disambiguation | Category |
|---|---|---|
| `Bought To Open` | None needed — unambiguous options | `OPTIONS_BUY_TO_OPEN` |
| `Sold Short` (options) | Description matches options regex | `OPTIONS_SELL_TO_OPEN` |
| `Sold Short` (equity) | Description does NOT match options regex | `EQUITY_SELL` |
| `Sold To Close` | None needed — unambiguous options | `OPTIONS_SELL_TO_CLOSE` |
| `Bought To Cover` (options) | Description matches options regex | `OPTIONS_BUY_TO_CLOSE` |
| `Bought To Cover` (equity) | Description does NOT match options regex | `EQUITY_BUY` |

**Implementation notes:**
- `Bought To Open` → `OPTIONS_BUY_TO_OPEN`: no description check needed
- `Sold To Close` → `OPTIONS_SELL_TO_CLOSE`: no description check needed
- `Sold Short` and `Bought To Cover` still require the description-field options regex for disambiguation
- Unit tests must cover BOTH activity type paths for BUY-TO-OPEN and SELL-TO-CLOSE:
  - `Bought To Open` + `Sold Short` (options) both → `OPTIONS_BUY_TO_OPEN` / `OPTIONS_SELL_TO_OPEN`
  - `Sold To Close` + `Bought To Cover` (options) both → `OPTIONS_SELL_TO_CLOSE` / `OPTIONS_BUY_TO_CLOSE`
  - `Sold Short` (equity) + `Bought To Cover` (equity) paths → correct equity categories
- 100% branch coverage required on disambiguation paths
