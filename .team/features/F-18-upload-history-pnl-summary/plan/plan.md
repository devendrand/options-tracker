# F-18: Upload History Page + P&L Summary Page

**Feature:** F-18  
**Owner:** angular-tdd-frontend  
**Status:** Updated — `entries` → `items`, total P&L derived client-side (per tech-lead conditions)  
**Depends on:** F-14 (Angular Core Services), F-12 (Upload API), F-13 (P&L API), F-17 (pnl.model.ts corrections)

---

## Open Question Resolutions (Previously Captured)

### OQ3 — P&L Summary Period Aggregation (Resolved 2026-03-30)
One period at a time. Toggle between Year / Month. Default: Year. API param: `?period=year|month`.

---

## 1. Objectives

### Upload History (`/uploads`)
- List all uploads with status badges
- Allow soft-deleting an upload with a confirmation step and warning message
- Show empty state when no uploads exist

### P&L Summary (`/pnl-summary`)
- Toggle between Year and Month period views
- Display a table of P&L by period bucket
- Optional underlying filter
- Empty state when no closed positions exist

---

## 2. Scope

### 2.1 Files to create

| File | Purpose |
|---|---|
| `features/upload-history/upload-history.component.ts` | Upload list + delete flow |
| `features/upload-history/upload-history.component.html` | Upload History template |
| `features/upload-history/upload-history.component.spec.ts` | Jest tests |
| `features/pnl-summary/pnl-summary.component.ts` | P&L summary with period toggle |
| `features/pnl-summary/pnl-summary.component.html` | P&L Summary template |
| `features/pnl-summary/pnl-summary.component.spec.ts` | Jest tests |

### 2.2 Model corrections (owned by F-17, consumed by F-18)

`pnl.model.ts` corrections are made as part of F-17 scope (see F-17 plan Section 2.2). F-18 implements against the already-corrected interfaces. The corrected shapes are:

```typescript
// PnlPeriodEntry — aligned with backend PnlPeriodResponse
export interface PnlPeriodEntry {
  period_label: string;
  options_pnl: string;
  equity_pnl: string;
  total_pnl: string;
  // realized_pnl and trade_count REMOVED — do not exist in backend response
}

// PnlSummary — aligned with backend PnlSummaryResponse
export interface PnlSummary {
  period: string;
  items: PnlPeriodEntry[];  // was entries — corrected to match backend
  // total_realized_pnl REMOVED — does not exist in backend response
  // Derive total P&L client-side: items.reduce((s, e) => s + parseFloat(e.total_pnl), 0)
}

// PnlQueryParams — underlying support required for F-18 filter
export interface PnlQueryParams {
  period?: PnlPeriod;
  underlying?: string;   // ADD — needed for underlying filter in PnlSummaryComponent
  start_date?: string;
  end_date?: string;
}
```

If F-17 has not yet merged when F-18 implementation begins, make these corrections in F-18 instead. Do not duplicate corrections if F-17 has already applied them.

---

## 3. UploadHistoryComponent

### 3.1 Architecture

```
UploadHistoryComponent (standalone, OnPush)
  ├── inject(UploadService)
  ├── _uploads: signal<Upload[]>([])
  ├── _loading: signal<boolean>(false)
  ├── _error: signal<string | null>(null)
  └── _deletingId: signal<string | null>(null)   // ID of upload pending delete confirmation
```

### 3.2 Data Loading

`ngOnInit()` calls `loadUploads()`:

```typescript
loadUploads(): void {
  this._loading.set(true);
  this._error.set(null);
  this.uploadService.getUploads().subscribe({
    next: (uploads) => {
      this._uploads.set(uploads);
      this._loading.set(false);
    },
    error: (err: { message?: string }) => {
      this._error.set(err?.message ?? 'Failed to load uploads.');
      this._loading.set(false);
    },
  });
}
```

### 3.3 Table Columns

| Column | Source | Notes |
|---|---|---|
| Filename | `upload.filename` | |
| Broker | `upload.broker` | |
| Status | `upload.status` | Use `StatusBadgeComponent` |
| Rows | `upload.row_count ?? '—'` | |
| Options | `upload.options_count ?? '—'` | |
| Duplicates | `upload.duplicate_count ?? '—'` | |
| Parse Errors | `upload.parse_error_count ?? '—'` | Highlight if > 0 |
| Uploaded | `upload.created_at` | Use `RelativeDatePipe` |
| Actions | Delete button | |

### 3.4 Delete Flow

Soft-delete is destructive and irreversible (position data may be affected). The flow is:

1. User clicks "Delete" on a row → `_deletingId.set(upload.id)`
2. A confirmation inline panel appears below the row (or in the Actions cell) showing:
   > **Warning:** Deleting this upload may surface previously hidden duplicate transactions. Review the Transactions page after deletion.
   - "Confirm Delete" button → calls `confirmDelete(upload.id)`
   - "Cancel" button → `_deletingId.set(null)`
3. `confirmDelete(id)`:
   - Calls `uploadService.deleteUpload(id)`
   - On success: removes the upload from `_uploads` signal (filter out by id), `_deletingId.set(null)`
   - On error: shows inline error message in the confirmation panel, stays open

`data-testid` attributes:
- `upload-row-{id}`
- `delete-btn-{id}` — initial delete button
- `confirm-panel-{id}` — confirmation inline panel (only visible when `_deletingId()` === id)
- `confirm-delete-btn-{id}`
- `cancel-delete-btn-{id}`
- `delete-warning-text`

Only one confirmation panel is open at a time — setting a new `_deletingId` implicitly closes the previous one.

### 3.5 Template States

| State | Condition | `data-testid` |
|---|---|---|
| Loading spinner | `_loading()` | `loading-state` |
| Error alert | `_error()` non-null | `error-state` |
| Empty state | no loading, no error, 0 uploads | `empty-state` |
| Uploads table | no loading, no error, uploads > 0 | `uploads-table` |

### 3.6 UploadHistoryComponent TDD

1. Component creates without error
2. Calls `uploadService.getUploads()` on `ngOnInit`
3. Loading state shown while request is in-flight
4. Uploads table rendered on success with correct row count
5. Filename, broker, status visible in first row
6. `StatusBadgeComponent` used for status column
7. Empty state shown when `getUploads()` returns `[]`
8. Error state shown on API failure with error message
9. "Retry" button in error state calls `loadUploads()` again
10. Delete button present for each row
11. Clicking delete shows confirmation panel for that row
12. Confirmation panel contains warning text
13. Clicking Cancel hides the confirmation panel
14. Clicking Cancel does not call `deleteUpload()`
15. Clicking Confirm Delete calls `uploadService.deleteUpload(id)`
16. After successful delete, row is removed from the table
17. `_deletingId` is cleared after successful delete
18. On delete error, confirmation panel stays open with error message
19. Opening a second delete confirmation closes the first (only one panel at a time)
20. Null row_count renders `—`

---

## 4. PnlSummaryComponent

### 4.1 Architecture

```
PnlSummaryComponent (standalone, OnPush)
  ├── inject(PnlService)
  ├── _summary: signal<PnlSummary | null>(null)
  ├── _loading: signal<boolean>(false)
  ├── _error: signal<string | null>(null)
  ├── _period: signal<PnlPeriod>('year')        // default Year
  └── _underlying: signal<string>('')
```

**Computed total P&L (client-side — `total_realized_pnl` does not exist in API response):**

```typescript
readonly totalPnl = computed(() => {
  const items = this._summary()?.items ?? [];
  return items.reduce((sum, e) => sum + parseFloat(e.total_pnl), 0).toFixed(2);
});
```

Display `totalPnl()` at the top of the page as a summary headline with green/red colouring.

### 4.2 Period Toggle + Underlying Filter

**Period toggle:**
```html
<div data-testid="period-toggle">
  <label>
    <input type="radio" name="period" value="year" [checked]="_period() === 'year'"
           (change)="setPeriod('year')"> Year
  </label>
  <label>
    <input type="radio" name="period" value="month" [checked]="_period() === 'month'"
           (change)="setPeriod('month')"> Month
  </label>
</div>
```

`setPeriod(period: PnlPeriod)`: sets `_period` signal → calls `loadSummary()`

**Underlying filter:**
```html
<input type="text" placeholder="Filter by underlying (e.g. NVDA)"
       [value]="_underlying()" (input)="setUnderlying($event)"
       data-testid="underlying-filter">
```

`setUnderlying(event)`: sets `_underlying` from input value → calls `loadSummary()`

### 4.3 Data Loading

```typescript
loadSummary(): void {
  this._loading.set(true);
  this._error.set(null);

  const params: PnlQueryParams = { period: this._period() };
  if (this._underlying()) params.underlying = this._underlying();

  this.pnlService.getSummary(params).subscribe({
    next: (summary) => {
      this._summary.set(summary);
      this._loading.set(false);
    },
    error: (err: { message?: string }) => {
      this._error.set(err?.message ?? 'Failed to load P&L summary.');
      this._loading.set(false);
    },
  });
}
```

`ngOnInit()` calls `loadSummary()` with defaults (`period: 'year'`, no underlying).

### 4.4 P&L Summary Table

Columns (aligned with F-13 OQ1 resolution):

| Column | Source | Notes |
|---|---|---|
| Period | `entry.period_label` | Format using `formatPeriodLabel()` |
| Options P&L | `entry.options_pnl` | Green/red styling |
| Equity P&L | `entry.equity_pnl` | Green/red styling |
| Total P&L | `entry.total_pnl` | Bold; green/red |

**`formatPeriodLabel(label: string, period: PnlPeriod): string`** — pure formatting method (not a separate pipe):
- `period === 'month'`: `'2026-03'` → `'Mar 2026'`
- `period === 'year'`: `'2026'` → `'2026'`

Implementation:
```typescript
formatPeriodLabel(label: string, period: PnlPeriod): string {
  if (period === 'month') {
    const [year, month] = label.split('-');
    const date = new Date(Number(year), Number(month) - 1, 1);
    return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
  }
  return label;
}
```

Sorted chronologically ascending — backend returns data sorted; no client-side sort needed.

### 4.5 Template States

| State | Condition | `data-testid` |
|---|---|---|
| Loading spinner | `_loading()` | `loading-state` |
| Error alert | `_error()` non-null | `error-state` |
| Empty state | no loading, no error, `(_summary()?.items?.length ?? 0) === 0` | `empty-state` |
| Summary table | no loading, no error, `items.length > 0` | `pnl-table` |

The page headline shows `totalPnl()` computed signal (sum of `items[].total_pnl`) — **not** a non-existent `total_realized_pnl` API field.

### 4.6 PnlSummaryComponent TDD

1. Component creates without error
2. Calls `pnlService.getSummary({ period: 'year' })` on `ngOnInit` (default period)
3. Loading state shown while request is in-flight
4. P&L table rendered on success with correct number of rows
5. Year toggle is selected by default
6. Switching to Month toggle calls `loadSummary()` with `period: 'month'`
7. Month period_label `'2026-03'` displayed as `'Mar 2026'`
8. Year period_label `'2026'` displayed as `'2026'`
9. Positive `total_pnl` has green styling class
10. Negative `total_pnl` has red styling class
11. Options P&L column shows `entry.options_pnl`
12. Equity P&L column shows `entry.equity_pnl`
13. Empty state shown when `entries` is empty
14. Error state shown on failure with error message
15. Entering underlying `'NVDA'` calls `loadSummary()` with `underlying: 'NVDA'` param
16. Clearing underlying filter calls `loadSummary()` without `underlying` param
17. `formatPeriodLabel()` with `'month'` and `'2026-12'` returns `'Dec 2026'`
18. `formatPeriodLabel()` with `'year'` and `'2025'` returns `'2025'`

---

## 5. Quality Gates

```bash
cd frontend
npx ng lint                              # ESLint clean
npx prettier --check .                   # Formatting clean
npx jest --coverage --ci                 # 100% lines, branches, functions, statements
npx ng build --configuration production  # Production build succeeds
```

---

## 6. Implementation Order

1. **Update `pnl.model.ts`** — add `underlying` to `PnlQueryParams`; update `PnlPeriodEntry` shape (options_pnl, equity_pnl, total_pnl); update `pnl.service.ts` to pass `underlying` param; update `pnl.service.spec.ts`
2. **`UploadHistoryComponent`** — write 20 tests, then implement TS + HTML
3. **`PnlSummaryComponent`** — write 18 tests, then implement TS + HTML
4. Run full quality gate

---

## 7. Acceptance Criteria

```
Given the Upload History page loads
When getUploads() returns 3 uploads
Then 3 rows are shown in the table
And each row has a "Delete" button

Given the user clicks "Delete" on upload U1
Then a confirmation panel appears with the warning message
And a "Confirm Delete" and "Cancel" button are visible

Given the user clicks "Cancel"
Then the confirmation panel is hidden
And deleteUpload() was not called

Given the user clicks "Confirm Delete"
When deleteUpload() succeeds
Then the row for U1 is removed from the table

Given the P&L Summary page loads
Then the Year toggle is selected
And getSummary({ period: 'year' }) is called

Given the user switches to Month
Then getSummary({ period: 'month' }) is called
And period_label '2026-03' is displayed as 'Mar 2026'

Given the user types 'NVDA' in the underlying filter
Then getSummary({ period: 'year', underlying: 'NVDA' }) is called

Given getSummary() returns entries: []
Then the empty state is displayed
```

---

## 8. Dependencies / Blockers

- **F-14 complete** — `UploadService`, `PnlService`, `StatusBadgeComponent`, `RelativeDatePipe` must be in place
- **F-12** — needed for live upload list data; component is testable with mocked service
- **F-13** — needed for live P&L data; `PnlPeriodEntry` model update should be done in this feature aligned with F-13 contract
- **Model coordination:** Align `PnlPeriodEntry` shape with backend-tdd-api-dev before implementing PnlSummaryComponent — if F-13 is not yet merged, use the agreed shape and mock data accordingly in tests
- No routing changes — `/uploads` and `/pnl-summary` routes are pre-wired from F-14
