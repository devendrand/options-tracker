# F-13: Transactions + Positions + P&L API Endpoints

**Feature:** F-13  
**Owner:** backend-tdd-api-dev  
**Status:** Pending plan  
**Depends on:** F-12 (Upload API)

---

## Open Question Resolutions Affecting This Feature

### OQ1 — Equity P&L in v0.1 (Resolved 2026-03-30)

**Resolution:** API endpoints must expose equity positions and include equity P&L in summary aggregations.

**Impact on `GET /api/v1/positions`:**
- Add `?asset_type=options|equity|all` query parameter (default: `options`)
- When `asset_type=equity` or `all`: return `EquityPosition` records in addition to / instead of `OptionsPosition`
- Equity position response shape must include: `underlying`, `quantity`, `cost_basis_per_share`, `status`, `source` (EQUITY_BUY / ASSIGNMENT / EXERCISE), `equity_realized_pnl`, `closed_at`

**Impact on `GET /api/v1/pnl/summary`:**
- Response must include both options and equity P&L per period bucket
- Response shape per item: `{ period_label: str, options_pnl: Decimal, equity_pnl: Decimal, total_pnl: Decimal }`
- `?type=options|equity|all` filter (default: `all`) may be added to allow filtering by asset type
- `?underlying=AAPL` filter applies to both options and equity positions for that underlying

---

### OQ3 — P&L Summary Period Aggregation (Resolved 2026-03-30)

**Resolution:** One period at a time is sufficient for v0.1. The `?period=month|year` parameter approach is confirmed correct.

**Impact on `GET /api/v1/pnl/summary`:**
- `?period=month` → group by calendar month of `transaction_date`; `period_label` format: `'2026-03'` (YYYY-MM)
- `?period=year` → group by calendar year of `transaction_date`; `period_label` format: `'2026'` (YYYY)
- Default period: `year` (broadest view on first load)
- Results sorted chronologically (ascending by period)
- No combined month+year response in a single call — one period type per request
- No new combined endpoint needed; existing `GET /api/v1/pnl/summary` with `?period=` is sufficient

**Test requirements:**
- Empty result set (no closed positions)
- Single month / single year with both options and equity P&L
- Multiple months spanning a year boundary
- `?underlying=NVDA` filter returning only NVDA positions' P&L
- Mix of positive and negative P&L periods
