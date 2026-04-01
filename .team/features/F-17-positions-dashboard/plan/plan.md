# F-17: Positions Page + Dashboard

**Feature:** F-17  
**Owner:** angular-tdd-frontend  
**Status:** Revised after tech-lead rejection — pending re-review  
**Depends on:** F-14 (Angular Core Services), F-13 (Positions + P&L API — for live data; also for leg schema extension)

---

## Open Question Resolutions (Previously Captured)

### OQ1 — Equity P&L in v0.1 (Resolved 2026-03-30)
Dashboard "Total Realized P&L" card combines options + equity P&L. Computed client-side by summing `items[].total_pnl`.

### OQ2 — Partial Close Display (Resolved 2026-03-30)
One row per `OptionsPosition` with an expandable detail drawer. Lazy-load drawer via `GET /api/v1/positions/{id}` on first expand.

---

## Changes from v1 (Tech-Lead Rejection Fixes)

| Issue | v1 (incorrect) | v2 (corrected) |
|---|---|---|
| Leg field `leg_type` | `leg.leg_type` | `leg.leg_role` (backend field name) |
| Leg detail columns | price/amount/commission/trade_date assumed present | Pending F-13 backend extension; plan specifies extended schema with explicit dependency |
| `PositionService.getPositions()` return type | `PaginatedResponse<OptionsPosition>` (has `.items`) | `PositionListResponse` (has `.options_items`, `.equity_items`) |
| `OptionsPosition` model | missing `option_symbol`, `direction` | both fields added; status enum extended to 6 values |
| `PnlSummary.entries` | `entries: PnlPeriodEntry[]` | `items: PnlPeriodEntry[]` (matches backend `PnlSummaryResponse`) |
| `total_realized_pnl` from API | `summary.total_realized_pnl` (field does not exist) | computed client-side: `sum(items[].total_pnl)` |
| `_expandedIds` mutation | direct Set mutation | immutable update: `new Set([...set, id])` / `new Set([...set].filter(...))` |
| `@Input() positionId` | decorator-based `@Input()` | `input()` signal (`InputSignal<string>`) per Angular 21 patterns |

---

## 1. Objectives

### Dashboard (`/dashboard`)
- Display summary cards: Total Realized P&L (combined options + equity, computed client-side), count of open options positions
- Show a CTA to upload if no data

### Positions Page (`/positions`)
- Display options positions in a paginated table (one row per position)
- Support expandable row drawers showing leg detail and P&L breakdown
- Filter controls: status, option type, underlying symbol
- Handle loading, error, and empty states

---

## 2. Required Model Corrections

These model file updates must be done as part of F-17 implementation. They align frontend models with the actual backend schemas in `backend/app/schemas/`.

### 2.1 `core/models/position.model.ts` — full replacement

```typescript
export type OptionType = 'CALL' | 'PUT';
export type PositionDirection = 'LONG' | 'SHORT';
export type OptionsPositionStatus =
  | 'OPEN'
  | 'PARTIALLY_CLOSED'
  | 'CLOSED'
  | 'EXPIRED'
  | 'ASSIGNED'
  | 'EXERCISED';

// Leg schema — requires F-13 backend extension for price/amount/commission/trade_date
// See Section 5 for drawer behaviour with and without extended fields
export interface OptionsPositionLeg {
  id: string;
  transaction_id: string;
  leg_role: 'OPEN' | 'CLOSE';      // was leg_type — corrected to match backend LegRole
  quantity: string;
  // Following 4 fields require OptionsPositionLegResponse extension in F-13:
  price: string;
  amount: string;
  commission: string;
  trade_date: string;
}

// List-level position (no legs — legs array absent in list response)
export interface OptionsPosition {
  id: string;
  underlying: string;
  option_symbol: string;            // ADD — present in OptionsPositionResponse
  option_type: OptionType;
  direction: PositionDirection;     // ADD — present in OptionsPositionResponse
  strike: string;
  expiry: string;
  status: OptionsPositionStatus;
  is_covered_call: boolean;
  realized_pnl: string | null;
}

// Detail-level position (includes legs — from GET /api/v1/positions/{id})
export interface OptionsPositionDetail extends OptionsPosition {
  legs: OptionsPositionLeg[];
}

export interface PositionQueryParams {
  offset?: number;
  limit?: number;
  underlying?: string;
  status?: OptionsPositionStatus;
  option_type?: OptionType;
}

// Replaces PaginatedResponse<OptionsPosition> — backend PositionListResponse shape
export interface PositionListResponse {
  total: number;
  offset: number;
  limit: number;
  options_items: OptionsPosition[];
  equity_items: EquityPosition[];
}

export type EquityPositionStatus = 'OPEN' | 'CLOSED';
export type EquityPositionSource = 'PURCHASE' | 'ASSIGNMENT' | 'EXERCISE';

export interface EquityPosition {
  id: string;
  underlying: string;
  quantity: string;
  cost_basis_per_share: string;
  status: EquityPositionStatus;
  source: EquityPositionSource;
  equity_realized_pnl: string | null;
  closed_at: string | null;
}
```

### 2.2 `core/models/pnl.model.ts` — update to match `PnlSummaryResponse`

```typescript
export type PnlPeriod = 'month' | 'year';

// Aligned with backend PnlPeriodResponse
export interface PnlPeriodEntry {
  period_label: string;
  options_pnl: string;     // was realized_pnl (single field) — now split
  equity_pnl: string;
  total_pnl: string;
}

// Aligned with backend PnlSummaryResponse
// total_realized_pnl REMOVED — does not exist in backend response
// Compute total client-side: items.reduce((s, e) => s + parseFloat(e.total_pnl), 0)
export interface PnlSummary {
  period: string;          // backend sends string, not PnlPeriod | null
  items: PnlPeriodEntry[]; // was entries — corrected to match backend
}

export interface PnlQueryParams {
  period?: PnlPeriod;
  underlying?: string;
  start_date?: string;
  end_date?: string;
}
```

### 2.3 `core/services/position.service.ts` — update return types

```typescript
// getPositions() now returns PositionListResponse (not PaginatedResponse<OptionsPosition>)
getPositions(params?: PositionQueryParams): Observable<PositionListResponse>

// getPosition() now returns OptionsPositionDetail (not OptionsPosition)
getPosition(id: string): Observable<OptionsPositionDetail>
```

Update `position.service.spec.ts` mock shapes to match `PositionListResponse`.

### 2.4 `core/services/pnl.service.ts` — add `underlying` param support

```typescript
// PnlQueryParams already has underlying?: string — ensure it is passed as HTTP param
if (params.underlying) {
  httpParams = httpParams.set('underlying', params.underlying);
}
```

---

## 3. Scope

### 3.1 Files to create / update

| File | Action | Purpose |
|---|---|---|
| `core/models/position.model.ts` | Update | Correct all model mismatches (see Section 2.1) |
| `core/models/pnl.model.ts` | Update | Align with backend PnlSummaryResponse (see Section 2.2) |
| `core/services/position.service.ts` | Update | Correct return types (see Section 2.3) |
| `core/services/position.service.spec.ts` | Update | Fix mock shapes |
| `core/services/pnl.service.ts` | Update | Add `underlying` param support |
| `core/services/pnl.service.spec.ts` | Update | Fix mock shapes |
| `features/dashboard/dashboard.component.ts` | Create | Dashboard summary cards |
| `features/dashboard/dashboard.component.html` | Create | Dashboard template |
| `features/dashboard/dashboard.component.spec.ts` | Create | Jest tests |
| `features/positions/positions.component.ts` | Create | Positions list + drawers |
| `features/positions/positions.component.html` | Create | Positions template |
| `features/positions/positions.component.spec.ts` | Create | Jest tests |
| `features/positions/position-drawer/position-drawer.component.ts` | Create | Lazy leg detail drawer |
| `features/positions/position-drawer/position-drawer.component.html` | Create | Drawer template |
| `features/positions/position-drawer/position-drawer.component.spec.ts` | Create | Jest tests |

---

## 4. DashboardComponent

### 4.1 Architecture

```
DashboardComponent (standalone, OnPush)
  ├── inject(PnlService)
  ├── inject(PositionService)
  ├── _pnlItems: signal<PnlPeriodEntry[]>([])
  ├── _openPositionCount: signal<number | null>(null)
  ├── _pnlLoading: signal<boolean>(false)
  ├── _positionsLoading: signal<boolean>(false)
  ├── _pnlError: signal<string | null>(null)
  └── _positionsError: signal<string | null>(null)
```

**Computed total P&L (client-side — `total_realized_pnl` does not exist in backend response):**

```typescript
readonly totalPnl = computed(() =>
  this._pnlItems()
    .reduce((sum, entry) => sum + parseFloat(entry.total_pnl), 0)
    .toFixed(2)
);

readonly hasData = computed(() =>
  parseFloat(this.totalPnl()) !== 0 || (this._openPositionCount() ?? 0) > 0
);
```

### 4.2 Data loading

On `ngOnInit`, fire two parallel calls:

```typescript
// Call 1: Year-view P&L for broadest summary
this.pnlService.getSummary({ period: 'year' }).subscribe({
  next: (summary) => {
    this._pnlItems.set(summary.items);    // was summary.entries
    this._pnlLoading.set(false);
  },
  error: (err: { message?: string }) => {
    this._pnlError.set(err?.message ?? 'Failed to load P&L.');
    this._pnlLoading.set(false);
  },
});

// Call 2: Open positions count
this.positionService.getPositions({ status: 'OPEN', limit: 1 }).subscribe({
  next: (response) => {
    this._openPositionCount.set(response.total);  // PositionListResponse.total
    this._positionsLoading.set(false);
  },
  error: (err: { message?: string }) => {
    this._positionsError.set(err?.message ?? 'Failed to load positions.');
    this._positionsLoading.set(false);
  },
});
```

### 4.3 Template

```
[Dashboard page]
  ┌───────────────────────┐  ┌─────────────────────┐
  │  Total Realized P&L   │  │  Open Positions      │
  │  $1,234.56 (green)    │  │  12                  │
  └───────────────────────┘  └─────────────────────┘

  [If !hasData(): "Upload your first CSV" CTA → routerLink /upload]
```

P&L card colour rules:
- `parseFloat(totalPnl()) > 0` → green
- `parseFloat(totalPnl()) < 0` → red
- `=== 0` → neutral

`data-testid` attributes:
- `pnl-card`, `pnl-value`, `pnl-loading`, `pnl-error`
- `open-positions-card`, `open-positions-value`, `open-positions-loading`, `open-positions-error`
- `no-data-cta` (shown when `!hasData()`)

### 4.4 DashboardComponent TDD (12 tests)

1. Component creates without error
2. Calls `pnlService.getSummary({ period: 'year' })` on `ngOnInit`
3. Calls `positionService.getPositions({ status: 'OPEN', limit: 1 })` on `ngOnInit`
4. P&L card shows loading spinner while pnl request is in-flight
5. Open positions card shows loading spinner while positions request is in-flight
6. Positive `totalPnl` rendered with green styling class
7. Negative `totalPnl` rendered with red styling class
8. `totalPnl` computed as sum of `items[].total_pnl` (e.g. `["100.00", "50.00"]` → `"150.00"`)
9. Open position count rendered from `response.total`
10. P&L error message shown when pnlService fails
11. Open positions error shown when positionService fails
12. No-data CTA shown when totalPnl is `"0.00"` and open count is 0

---

## 5. PositionsComponent

### 5.1 Architecture

```
PositionsComponent (standalone, OnPush)
  ├── inject(PositionService)
  ├── _positions: signal<OptionsPosition[]>([])
  ├── _total: signal<number>(0)
  ├── _loading: signal<boolean>(false)
  ├── _error: signal<string | null>(null)
  ├── _offset: signal<number>(0)
  ├── _limit: signal<number>(100)
  ├── _underlying: signal<string>('')
  ├── _status: signal<OptionsPositionStatus | ''>('')
  ├── _optionType: signal<OptionType | ''>('')
  └── _expandedIds: signal<ReadonlySet<string>>(new Set())
```

**Immutable Set updates (required for OnPush change detection):**

```typescript
toggleDrawer(id: string): void {
  const current = this._expandedIds();
  if (current.has(id)) {
    this._expandedIds.set(new Set([...current].filter(i => i !== id)));
  } else {
    this._expandedIds.set(new Set([...current, id]));
  }
}

isExpanded(id: string): boolean {
  return this._expandedIds().has(id);
}
```

**Computed pagination:**
```typescript
readonly totalPages = computed(() => Math.ceil(this._total() / this._limit()));
readonly currentPage = computed(() => Math.floor(this._offset() / this._limit()) + 1);
readonly hasPrev = computed(() => this._offset() > 0);
readonly hasNext = computed(() => this._offset() + this._limit() < this._total());
```

### 5.2 Data Loading

```typescript
loadPositions(): void {
  this._loading.set(true);
  this._error.set(null);

  const params: PositionQueryParams = {
    offset: this._offset(),
    limit: this._limit(),
  };
  if (this._underlying()) params.underlying = this._underlying();
  if (this._status()) params.status = this._status() as OptionsPositionStatus;
  if (this._optionType()) params.option_type = this._optionType() as OptionType;

  this.positionService.getPositions(params).subscribe({
    next: (response) => {
      this._positions.set(response.options_items);  // use options_items, not items
      this._total.set(response.total);
      this._loading.set(false);
    },
    error: (err: { message?: string }) => {
      this._error.set(err?.message ?? 'Failed to load positions.');
      this._loading.set(false);
    },
  });
}
```

### 5.3 Table Columns (OQ2 resolution + corrected model)

| Column | Source | Notes |
|---|---|---|
| Underlying | `position.underlying` | |
| Symbol | `position.option_symbol` | Full option symbol (e.g. `AAPL240119C00150000`) |
| Option Type | `position.option_type` | `CALL` / `PUT` |
| Direction | `position.direction` | `LONG` / `SHORT` |
| Strike | `position.strike` | `$XX.XX` |
| Expiry | `position.expiry` | Use `RelativeDatePipe` |
| Status | `position.status` | Use `StatusBadgeComponent`; covers all 6 values |
| Realized P&L | `position.realized_pnl ?? '—'` | Green if positive, red if negative |
| Covered Call | `position.is_covered_call` | Shield badge if true, empty if false |
| Expand | toggle button | `[data-testid="expand-btn-{id}"]` |

### 5.4 Filter Controls

| Control | Type | Values | API param |
|---|---|---|---|
| Status | `<select>` | All, OPEN, PARTIALLY_CLOSED, CLOSED, EXPIRED, ASSIGNED, EXERCISED | `status` |
| Option Type | `<select>` | All, CALL, PUT | `option_type` |
| Underlying | `<input type="text">` | free text | `underlying` |
| Reset | `<button>` | calls `resetFilters()` | — |

Changing any filter resets `_offset` to 0 and calls `loadPositions()`.

### 5.5 Expandable Drawers

```html
@for (position of _positions(); track position.id) {
  <tr [attr.data-testid]="'position-row-' + position.id">
    <!-- ... cells ... -->
    <td>
      <button (click)="toggleDrawer(position.id)"
              [attr.data-testid]="'expand-btn-' + position.id">
        {{ isExpanded(position.id) ? 'Collapse' : 'Expand' }}
      </button>
    </td>
  </tr>
  @if (isExpanded(position.id)) {
    <tr [attr.data-testid]="'drawer-row-' + position.id">
      <td colspan="10">
        <app-position-drawer [positionId]="position.id" />
      </td>
    </tr>
  }
}
```

Multiple drawers may be open simultaneously — `_expandedIds` tracks all expanded IDs.

### 5.6 Template States

| State | Condition | `data-testid` |
|---|---|---|
| Loading spinner | `_loading()` | `loading-state` |
| Error alert | `_error()` non-null | `error-state` |
| Empty state | not loading, no error, 0 rows | `empty-state` |
| Positions table | not loading, no error, rows > 0 | `positions-table` |

### 5.7 PositionsComponent TDD (26 tests)

**Initial state:**
1. Component creates without error
2. Calls `positionService.getPositions()` on `ngOnInit` with `{ offset: 0, limit: 100 }`
3. Loading state shown during request

**Data rendering:**
4. Table rendered on success using `response.options_items` (not `.items`)
5. Correct number of rows rendered
6. Underlying, option_symbol, direction, status visible in first row
7. `StatusBadgeComponent` used in status column
8. Covered call badge shown when `is_covered_call` is true
9. Covered call badge absent when `is_covered_call` is false
10. Empty state shown when `options_items` is `[]`

**Expand/collapse (immutable Set):**
11. Expand button present for each row
12. Clicking expand renders `PositionDrawerComponent` for that row
13. Clicking expand again collapses the drawer
14. Two drawers can be open simultaneously — both drawer rows in DOM after two expand clicks
15. Collapsing P1 drawer does not collapse P2 drawer
16. Each `toggleDrawer()` call creates a new `Set` reference (immutable update)

**Filters:**
17. Status dropdown has All + 6 status options
18. Selecting status OPEN calls `loadPositions()` with `{ status: 'OPEN', offset: 0 }`
19. Selecting CALL option type includes `option_type: 'CALL'`
20. Typing underlying includes `underlying` param
21. Reset clears all filters and reloads with defaults

**Pagination:**
22. Pagination controls present when total > limit
23. Previous disabled on page 1
24. Next disabled on last page
25. Next page advances offset by limit and calls `loadPositions()`

**Error handling:**
26. Error state shown on failure; Retry button calls `loadPositions()` again

---

## 6. PositionDrawerComponent

### 6.1 Architecture

```
PositionDrawerComponent (standalone, OnPush)
  ├── positionId = input.required<string>()   // input() signal — Angular 21 pattern
  ├── inject(PositionService)
  ├── _position: signal<OptionsPositionDetail | null>(null)
  ├── _loading: signal<boolean>(false)
  └── _error: signal<string | null>(null)
```

`input.required<string>()` replaces decorator-based `@Input()` per Angular 21 patterns.

### 6.2 Behaviour

`ngOnInit()` calls `this.positionService.getPosition(this.positionId())`.

Only fired on first render (because the component is created inside `@if (isExpanded(position.id))`).

### 6.3 Leg Detail Columns

**Dependency:** The 4 extended fields (`price`, `amount`, `commission`, `trade_date`) require `OptionsPositionLegResponse` to be extended in the backend (F-13 task for backend-tdd-api-dev). The drawer is designed for the extended schema. If F-13 has not yet shipped the extension, `price`, `amount`, `commission`, `trade_date` will be `undefined` in the response and the drawer must show `—` for those cells via null-coalescing.

| Column | Source | Notes |
|---|---|---|
| Date | `leg.trade_date ?? '—'` | `RelativeDatePipe`; `—` until F-13 extends backend schema |
| Role | `leg.leg_role` | `OPEN` or `CLOSE` |
| Quantity | `leg.quantity` | |
| Price | `leg.price ?? '—'` | `—` until F-13 extends backend schema |
| Cash Flow | `leg.amount ?? '—'` | Green if positive, red if negative; `—` until F-13 extends |
| Commission | `leg.commission ?? '—'` | `—` until F-13 extends backend schema |

**Per-pair P&L** (shown below each matched OPEN+CLOSE pair, computed client-side):

```typescript
pairPnl(open: OptionsPositionLeg, close: OptionsPositionLeg): string | null {
  if (!open.amount || !close.amount || !open.commission || !close.commission) {
    return null;  // fields not yet available from backend
  }
  const pnl = parseFloat(open.amount)
    + parseFloat(close.amount)
    - Math.abs(parseFloat(open.commission))
    - Math.abs(parseFloat(close.commission));
  return pnl.toFixed(2);
}
```

If `pairPnl()` returns `null`, show `—` for the P&L line. No partial P&L display is better than a wrong number.

For partially-closed positions:
- Render matched OPEN+CLOSE pairs with per-pair P&L
- Render remaining unmatched OPEN legs at the bottom with `—` in CLOSE/P&L positions

Grouping logic note: the backend returns a flat `legs[]` array with `leg_role` field. The drawer must pair `OPEN` legs with `CLOSE` legs in order. Since the backend uses FIFO matching, pair `legs.filter(l => l.leg_role === 'OPEN')` with `legs.filter(l => l.leg_role === 'CLOSE')` by index — first OPEN with first CLOSE, etc. Remaining unmatched OPENs are displayed last.

### 6.4 `data-testid` attributes

- `drawer-loading`
- `drawer-error`
- `drawer-retry-btn`
- `drawer-content`
- `leg-row-{leg.id}`

### 6.5 PositionDrawerComponent TDD (14 tests)

1. Component creates without error
2. Calls `positionService.getPosition(positionId())` on `ngOnInit` using `input()` signal value
3. Shows loading spinner while request is in-flight
4. Renders leg rows after successful response — one row per leg
5. `leg_role` value `'OPEN'` displayed in Role column
6. `leg_role` value `'CLOSE'` displayed in Role column
7. Quantity displayed for each leg
8. Positive `amount` has green styling class (when extended schema available)
9. Negative `amount` has red styling class (when extended schema available)
10. `amount` shows `'—'` when field is absent (null-coalescing before F-13 extension)
11. Error state shown when `getPosition()` fails
12. "Retry" button calls `getPosition()` again
13. Loading clears after error
14. `pairPnl()` returns `null` when `amount`/`commission` are absent; shows `—` in template

---

## 7. Quality Gates

```bash
cd frontend
npx ng lint                              # ESLint clean
npx prettier --check .                   # Formatting clean
npx jest --coverage --ci                 # 100% lines, branches, functions, statements
npx ng build --configuration production  # Production build succeeds
```

---

## 8. Implementation Order

1. **Model + service corrections** (prerequisite for everything else):
   - Update `position.model.ts` (full replacement)
   - Update `pnl.model.ts` (`entries` → `items`, remove `total_realized_pnl`, update `PnlPeriodEntry`)
   - Update `position.service.ts` return types
   - Update `pnl.service.ts` to pass `underlying` param
   - Fix `position.service.spec.ts` and `pnl.service.spec.ts` mock shapes
   - Run `npx jest --coverage --ci` — all existing tests pass

2. **`PositionDrawerComponent`** — write 14 tests, then implement TS + HTML

3. **`DashboardComponent`** — write 12 tests, then implement TS + HTML

4. **`PositionsComponent`** — write 26 tests, then implement TS + HTML

5. Run full quality gate pass

---

## 9. Acceptance Criteria

```
Given the positions page loads
When getPositions() returns PositionListResponse with 5 options_items
Then 5 rows are shown using response.options_items (not .items)
And each row shows: underlying, option_symbol, direction, status, strike, expiry

Given the user clicks "Expand" on position row P1
When the drawer opens
Then GET /api/v1/positions/P1 is called
And a loading spinner is shown during the fetch
And leg rows rendered with leg_role (not leg_type) values

Given positions P1 and P2 have their drawers open
When the user collapses P1
Then P1 drawer is hidden and P2 drawer remains visible
And each toggleDrawer() call produces a new Set reference

Given the dashboard loads with 3 P&L items: total_pnl = ["100.00", "-30.00", "200.00"]
Then the P&L card shows "270.00" (sum) with green styling
(Not reading non-existent total_realized_pnl field from API)

Given the dashboard loads with all items having total_pnl = "0.00" and open count = 0
Then the no-data CTA is shown

Given the PositionDrawerComponent receives a position where leg.amount is undefined
(before F-13 extends OptionsPositionLegResponse)
Then the Cash Flow column shows "—" via null-coalescing
And pairPnl() returns null → P&L row shows "—"
```

---

## 10. Dependencies / Blockers

- **F-14 complete** — `PositionService`, `PnlService`, `RelativeDatePipe`, `StatusBadgeComponent` must be in place
- **F-13** — needed for live data; also needed to extend `OptionsPositionLegResponse` with `price`, `amount`, `commission`, `trade_date`. Drawer is designed to degrade gracefully (shows `—`) before the backend extension ships, but full drawer functionality requires it.
- **Model corrections in this feature** — `position.model.ts`, `pnl.model.ts`, `position.service.ts` corrections are part of F-17 scope (not deferred). Existing services must be corrected before implementation of UI components begins.
- No routing changes — `/dashboard` and `/positions` pre-wired in F-14.
