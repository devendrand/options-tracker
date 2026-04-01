# F-06: E*TRADE CSV Parser

**Feature:** F-06  
**Owner:** backend-tdd-api-dev  
**Status:** Pending plan  
**Depends on:** F-05 (Database Schema)

---

## Open Question Resolutions Affecting This Feature

### OQ4 — DRIP Dividend Handling (Resolved 2026-03-30)

**Resolution:** No special handling required for DRIP rows in the parser.

Both DRIP rows (positive-amount dividend credit and negative-amount reinvestment debit) are passed through as standard `Dividend` activity type rows. The parser does NOT need to detect, pair, or link DRIP row pairs. Each row is yielded as a `ParsedTransaction` with `activity_type = 'Dividend'` and its original amount.

**Implementation notes:**
- No DRIP-specific regex or pairing logic in `etrade.py`
- The negative-amount DRIP debit row does NOT trigger `EquityPosition` creation in v0.1
- Both rows will appear on the Transactions page as `DIVIDEND` category with their respective signed amounts

---

### OQ5 — `Bought To Open` / `Sold To Close` Activity Type Support (Resolved 2026-03-30)

**Resolution:** Both E*TRADE activity type variants MUST be supported. This is a correctness requirement.

E*TRADE uses two different label sets depending on the order entry path:
- Options flow: `Bought To Open`, `Sold To Close` (unambiguous, no description regex needed)
- Equity/standard flow: `Sold Short`, `Bought To Cover` (require description-field regex to disambiguate options vs equity)

**Implementation notes:**
- The parser must surface the raw `Activity Type` field faithfully for all variants
- `Bought To Open` and `Sold To Close` are recognized as unambiguous options activity types — no description-field regex required in the classifier
- `Sold Short` and `Bought To Cover` require description regex (options regex pattern) to classify correctly
- CSV test fixtures must include rows for BOTH variants of each BUY-TO-OPEN and SELL-TO-CLOSE activity type
- At minimum 3 concrete description examples per variant for `Sold Short`/`Bought To Cover` (options + equity paths)
