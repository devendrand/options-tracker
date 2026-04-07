# F-17: Positions Page + Dashboard

**Feature:** F-17  
**Owner:** angular-tdd-frontend  
**Status:** v3 — Implementation in progress (all backend blockers resolved)  
**Depends on:** F-14 (Angular Core Services), F-13 backend extension (COMPLETED via Task #7)

---

## Implementation Addendum (v3 — 2026-04-01)

All three critical issues from the tech-lead v2 rejection are now resolved:

| Issue | Resolution |
|---|---|
| Leg schema missing `price/amount/commission/trade_date` | Task #7 completed — `OptionsPositionLegResponse` extended with all 4 fields |
| `leg_type` vs `leg_role` naming mismatch | Fixed in this implementation — model uses `leg_role` |
| `total_realized_pnl` absent from list response | Computed client-side from `items[].total_pnl`; present on detail response via `OptionsPositionDetailResponse.total_realized_pnl` |
| `PositionListResponse` shape (`options_items` not `items`) | Service updated to return `PositionListResponse` with `options_items`/`equity_items` |
| `OptionsPosition` missing `option_symbol`, `direction` | Added to model |

### Actual backend API (verified in `backend/app/schemas/position.py` and `backend/app/api/v1/positions.py`)

```
GET /api/v1/positions
  Params: asset_type, underlying, status, offset, limit
  Returns: PositionListResponse { total, offset, limit, options_items, equity_items }

GET /api/v1/positions/{id}
  Returns: OptionsPositionDetailResponse extends OptionsPositionResponse {
    legs: OptionsPositionLegResponse[],
    total_realized_pnl: Decimal | None
  }

OptionsPositionLegResponse: { id, transaction_id, leg_role, quantity, trade_date, price|None, amount, commission }
OptionsPositionResponse: { id, underlying, option_symbol, strike, expiry, option_type, direction, status, realized_pnl, is_covered_call }
```

---

## Original Plan (v2 — reference only, superseded by addendum above)

### Objectives

- **Dashboard** (`/dashboard`): P&L summary card, open/closed position counts, recent uploads (last 5), no-data CTA
- **Positions page** (`/positions`): paginated options positions table with expandable row drawers, filters, pagination
- **Position drawer** (sub-component): lazy-loads `GET /api/v1/positions/{id}` on first expand, shows all legs

### Architecture

#### DashboardComponent
- Calls `pnlService.getSummary({ period: 'year' })`, `positionService.getPositions({ status: 'OPEN', limit: 1 })`, `positionService.getPositions({ status: 'CLOSED', limit: 1 })`, `uploadService.getUploads()`
- Signals: `pnlItems`, `openCount`, `closedCount`, `recentUploads` (per-section loading/error)
- Computed: `totalPnl` (sum of `items[].total_pnl`), `isPnlPositive`, `isPnlNegative`, `hasData`

#### PositionsComponent
- Uses `expandedIds: signal<ReadonlySet<string>>(new Set())` — immutable Set updates for OnPush
- Reads `response.options_items` (not `response.items`)
- Renders `PositionDrawerComponent` (sub-component) for each expanded row

#### PositionDrawerComponent
- `positionId = input.required<string>()` (Angular 21 signal input)
- Calls `positionService.getPosition(positionId())` on `ngOnInit`
- Shows flat legs table: date, leg_role, qty, price, amount (with P&L class), commission

### Quality gate
- 100% line/branch/function/statement coverage
- `ng lint` + Prettier clean
- Production build succeeds
