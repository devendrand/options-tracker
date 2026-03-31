# OQ2: Partial Close Display

**Question:** When a position is `PARTIALLY_CLOSED`, should the UI show one row per leg pair or one row per position with a breakdown drawer?

**Resolution:** **One row per position with an expandable breakdown drawer.**

**Rationale:**
One row per leg pair creates O(n) table rows for a single economic position — a position scaled into 5 lots and partially closed creates a confusing, noisy table where the user cannot see the net exposure at a glance. The primary mental model for an options trader is "what is my current position in NVDA 220C?" — a single row answers that. The drill-down drawer satisfies the power user who wants to see individual leg economics without polluting the default view.

This also maps cleanly to the existing data model: `OptionsPosition` is the unit of display, and `OptionsPositionLeg` rows are the detail. The API already supports this pattern via `GET /api/v1/positions/{id}` which returns the full position with all legs and P&L breakdown.

For `PARTIALLY_CLOSED` positions specifically, the row should display:
- Open quantity (total)
- Closed quantity (matched so far)
- Realized P&L on the closed portion
- Unrealized indicator (e.g. a badge: "2 of 5 contracts closed")

**Impact on implementation:**
- Positions Page table: single row per `OptionsPosition` record — no change needed to data model or API
- Add expandable row/drawer component in Angular that calls `GET /api/v1/positions/{id}` on expand
- Positions table should show a visual indicator for `PARTIALLY_CLOSED` status (e.g. a colored badge)
- The drawer content should list each `OptionsPositionLeg` with its transaction date, quantity, price, and cash-flow amount
- Realized P&L in the main row = P&L on closed portion only; open portion shows cost basis only
