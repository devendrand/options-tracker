# OQ1: Equity P&L in v0.1

**Question:** Should `EQUITY_SELL` transactions close `EquityPosition` records and calculate equity realized P&L in v0.1, or defer to v1.0?

**Resolution:** Include equity P&L calculation in v0.1 as a **Should Have** feature.

**Rationale:**
The data model (`EquityPosition` with `equity_realized_pnl`, `close_transaction_id`, `closed_at`) already fully supports this in the schema. The domain logic is straightforward: `(sell_price − cost_basis_per_share) × quantity_sold`. More critically, equity positions are created from three sources — `EQUITY_BUY`, `OPTIONS_ASSIGNED`, and `OPTIONS_EXERCISED` — and assignment/exercise positions are a direct consequence of options activity. Leaving those equity lots untracked creates a blind spot for users managing covered calls and CSPs. Including equity P&L now also makes the Upload soft-delete cascade logic (`revert-to-OPEN` on close-leg deletion) consistent for both position types.

Deferral risk: if deferred, the `EquityPosition` table is populated but never read for analytics, which makes the Upload History page summary stats misleading. Users will expect to see the full financial picture in one tool.

**Impact on implementation:**
- `pnl.py` must handle `EquityPosition` close logic in addition to `OptionsPosition`
- `POST /api/v1/uploads` processing pipeline must call the equity close matcher after classifying `EQUITY_SELL` transactions
- `GET /api/v1/positions` should include an `?asset_type=options|equity|all` filter (default `options` for the Positions page; equity positions accessible via filter)
- `GET /api/v1/pnl/summary` must aggregate both options and equity realized P&L (or provide a `?type=options|equity|all` parameter)
- Dashboard summary card "Total Realized P&L" should reflect combined options + equity P&L
- No schema changes required — `EquityPosition.equity_realized_pnl` is already defined
