# F-16: Transactions Page (Updated)

**Feature:** F-16  
**Owner:** angular-tdd-frontend  
**Status:** In implementation — extending existing scaffold  
**Updated:** 2026-04-01

---

## 1. Current State

A working scaffold exists with:
- Paginated table (Date, Activity Type, Symbol, Description, Category, Qty, Price, Amount, Commission, Status)
- Single-select category filter, symbol text, date range
- 28 passing tests at 100% coverage

## 2. Delta — What Still Needs Building

| Requirement | Status |
|---|---|
| Category **multi**-select filter | ❌ Currently single-select |
| Status multi-select filter | ❌ Missing entirely |
| Upload column (links to `/uploads/{id}`) | ❌ Missing |
| Row visual distinction for DUPLICATE/POSSIBLE_DUPLICATE/PARSE_ERROR | ❌ StatusBadge exists but no row CSS |

---

## 3. Component Architecture Changes

### Signal changes
```typescript
// BEFORE
readonly category = signal<TransactionCategory | ''>('');

// AFTER
readonly selectedCategories = signal<TransactionCategory[]>([]);
readonly selectedStatuses   = signal<string[]>([]);
```

### New constant
```typescript
export const DEDUP_STATUSES = ['UNIQUE', 'DUPLICATE', 'POSSIBLE_DUPLICATE', 'PARSE_ERROR'] as const;
```

### New methods
```typescript
onCategoryMultiChange(event: Event): void  // reads selectedOptions[] → signal
onStatusMultiChange(event: Event): void     // reads selectedOptions[] → signal
rowClass(status: string): string            // returns 'row-duplicate' | 'row-possible-duplicate' | 'row-parse-error' | ''
```

### loadTransactions() param building (updated)
```typescript
if (this.selectedCategories().length) params.category = this.selectedCategories();
if (this.selectedStatuses().length)   params.dedup_status = this.selectedStatuses();
```

---

## 4. Model Changes

### `TransactionQueryParams` (transaction.model.ts)
```typescript
// category: TransactionCategory  → TransactionCategory[] (array)
// Add: dedup_status?: string[]
```

---

## 5. Service Changes

### `TransactionService.getTransactions()` (transaction.service.ts)
Array params serialised with `httpParams.append()` loop:
```typescript
if (params.category?.length) {
  params.category.forEach(c => httpParams = httpParams.append('category', c));
}
if (params.dedup_status?.length) {
  params.dedup_status.forEach(s => httpParams = httpParams.append('dedup_status', s));
}
```

---

## 6. Template Changes

### Upload column
```html
<th>Upload</th>
...
<td>
  <a [routerLink]="['/uploads', tx.upload_id]">{{ tx.upload_id | slice:0:8 }}</a>
</td>
```
Requires `RouterLink` and `SlicePipe` in component `imports`.

### Multi-select filters
```html
<select multiple data-testid="category-filter" (change)="onCategoryMultiChange($event)">
  @for (cat of categories; track cat) {
    <option [value]="cat">{{ cat | categoryLabel }}</option>
  }
</select>

<select multiple data-testid="status-filter" (change)="onStatusMultiChange($event)">
  @for (s of dedupStatuses; track s) {
    <option [value]="s">{{ s }}</option>
  }
</select>
```

### Row class binding
```html
<tr data-testid="transaction-row" [class]="rowClass(tx.dedup_status)">
```
CSS classes: `row-duplicate`, `row-possible-duplicate`, `row-parse-error`

---

## 7. TDD Test Plan (additions to existing 28)

### New tests for multi-select category filter
- Category multi-select renders all 15 options (no "All" option — deselect-all clears the filter)
- Selecting two categories sends `{ category: ['OPTIONS_SELL_TO_OPEN', 'OPTIONS_BUY_TO_OPEN'] }` to service
- Deselecting all categories (empty selection) omits category from params

### New tests for status filter
- Status filter renders 4 options: UNIQUE, DUPLICATE, POSSIBLE_DUPLICATE, PARSE_ERROR
- Selecting status sends `{ dedup_status: ['DUPLICATE'] }` to service
- Reset clears selectedStatuses signal

### New tests for Upload column
- Upload column header exists in table
- Upload cell contains an anchor with href to `/uploads/{upload_id}`
- Truncated upload_id (first 8 chars) displayed in link text

### New tests for row visual distinction
- Row with `dedup_status === 'DUPLICATE'` has class `row-duplicate`
- Row with `dedup_status === 'POSSIBLE_DUPLICATE'` has class `row-possible-duplicate`
- Row with `dedup_status === 'PARSE_ERROR'` has class `row-parse-error`
- Row with `dedup_status === 'UNIQUE'` has no special class

### Service spec additions
- `category: ['A', 'B']` serialises as two `category` query params
- `dedup_status: ['DUPLICATE', 'PARSE_ERROR']` serialises as two `dedup_status` params
- Empty arrays omit the param

### Updated existing tests
- Test 2: onInit call signature unchanged (no filters on init)
- Test 12 (category dropdown): update — multi-select renders 15 options, no "All Categories"
- Test 13 (category change): update to use `onCategoryMultiChange`
- Test 17 (offset reset): update to use new method
- Test 18 (reset): `selectedCategories` and `selectedStatuses` both reset to `[]`

---

## 8. Quality Gates

```bash
npx ng lint
npx prettier --check .
npx jest --coverage   # 100% lines, branches, functions, statements
npx tsc --project tsconfig.app.json --noEmit
```
