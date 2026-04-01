## PLAN REVIEW: F-18 — Upload History + P&L Summary Pages

**Reviewer:** tech-lead-architect
**Date:** 2026-04-01
**Plan file:** `.team/features/F-18-upload-history-pnl-summary/plan/plan.md`

---

### VERDICT: ⚠️ APPROVED WITH CONDITIONS

---

### Summary

The F-18 plan is well-structured with clear TDD plans (20 + 18 tests), a correct OQ3 resolution (year/month toggle), and a good delete confirmation UX. The `PnlPeriodEntry` model update is correctly identified. However, three pre-existing model mismatches in the service layer will cause runtime failures if not resolved before implementation begins. These are fixable with targeted model updates — no architectural rework is needed.

---

### Requirements Compliance: ✅ PASS

Upload History requirements:
- List uploads with status badges — ✅
- Soft-delete with confirmation + warning message — ✅ (two-step confirmation flow with `_deletingId` signal)
- Empty state — ✅
- Single confirmation panel at a time (one `_deletingId` signal) — ✅

P&L Summary requirements:
- Toggle between Year / Month (OQ3 resolution) — ✅
- Table of P&L by period — ✅
- Optional underlying filter — ✅
- Empty state — ✅

---

### API Contract Alignment: ❌ FAIL (conditions required)

#### Issue 1 — `PnlSummary` frontend model does not match `PnlSummaryResponse` backend schema

The plan correctly identifies that `PnlPeriodEntry` needs updating from `{period_label, realized_pnl, trade_count}` to `{period_label, options_pnl, equity_pnl, total_pnl}`. However, the `PnlSummary` wrapper interface also has two additional mismatches against `PnlSummaryResponse`:

Backend (`backend/app/schemas/pnl.py`):
```python
class PnlSummaryResponse(BaseModel):
    period: str
    items: list[PnlPeriodResponse]
```

Frontend (`core/models/pnl.model.ts`):
```typescript
export interface PnlSummary {
  total_realized_pnl: string;    // ← does not exist in backend response
  period: PnlPeriod | null;
  entries: PnlPeriodEntry[];     // ← backend uses "items", not "entries"
}
```

The plan uses `_summary()?.total_realized_pnl` in the template (Section 4.5) and `_summary()?.entries.length` in the empty state condition. Both will fail at runtime: `total_realized_pnl` will be `undefined`, and iterating `entries` will fail because the backend sends `items`.

**Required fix (part of Step 1 in implementation order):**
```typescript
export interface PnlSummary {
  period: string;
  items: PnlPeriodEntry[];
}
```
If `total_realized_pnl` is needed in the UI, compute it client-side: `items.reduce((sum, e) => sum + Number(e.total_pnl), 0)`. Update all plan references from `.entries` → `.items` and remove or derive `total_realized_pnl`.

Also update `PnlService.getSummary()` to pass through `underlying` param once `PnlQueryParams` is extended — the plan correctly identifies this need.

#### Issue 2 — `Upload` model field mismatch: `uploaded_at` vs `created_at`

The `UploadHistoryComponent` (Section 3.3) renders the "Uploaded" column from `upload.created_at` via `RelativeDatePipe`. However, the actual backend `UploadResponse` field is `uploaded_at`, not `created_at`. The `Upload` frontend interface has `created_at: string` and `updated_at: string` — neither of which exists in the backend response. The "Uploaded" column will always render a blank or pipe error.

**Required fix:** Update the `Upload` model (coordinated with the F-15 post-F-12 model update):
- Rename `created_at` → `uploaded_at: string`
- Remove `updated_at` (not in backend response)
- Remove `error_message` (not in backend response)
- Make counts non-nullable to match backend schema

Update the plan's table column to use `upload.uploaded_at` and update all spec mock fixtures.

#### Issue 3 — `UploadService.getUploads()` returns `Upload[]` but backend returns paginated `UploadListResponse`

The service is currently typed as `getUploads(): Observable<Upload[]>`, but the backend `/api/v1/uploads` returns `UploadListResponse: {total, offset, limit, items}`. At runtime, `uploads` in `loadUploads()` will be the full list-response object, not an array, so `_uploads.set(uploads)` will set the signal to an object rather than an array, causing template rendering failures.

**Required fix before F-18 implementation begins:**  
Update `UploadService.getUploads()` to handle the paginated response. Either:
- Return `Observable<UploadListResponse>` and update `UploadHistoryComponent` to read `response.items`
- Or add `.pipe(map(r => r.items))` in the service to maintain the `Observable<Upload[]>` return type

This is a service-layer fix, not a component-layer fix. It must be done as part of Step 1 in the implementation order, before `UploadHistoryComponent` tests are written.

---

### Code Coverage: ✅ PASS (when conditions are met)

- Upload History: 20 tests covering all component states, the full delete flow, and edge cases
- P&L Summary: 18 tests covering toggle, formatting, filter, empty state, error state
- `formatPeriodLabel()` tests 17–18 cover both period types with concrete input/output values — good practice for pure functions
- 100% coverage is achievable once model alignment is in place

---

### Architectural Alignment: ✅ PASS

- Both components: standalone, OnPush, `inject()` — consistent with project patterns
- `_deletingId: signal<string | null>` elegantly handles single-panel constraint
- Radio button period toggle is a clean, accessible implementation
- `formatPeriodLabel()` as a component method (not a separate pipe) is appropriate for a single-use formatter

---

### Issues Found

- [CRITICAL] `PnlSummary` model misaligns with backend on `total_realized_pnl` (non-existent) and `entries` vs `items` — see Issue 1 above.
- [CRITICAL] `Upload.created_at` does not exist in backend `UploadResponse` (`uploaded_at` is the correct field) — see Issue 2 above.
- [CRITICAL] `UploadService.getUploads()` pagination mismatch will prevent the upload list from rendering — see Issue 3 above.
- [MINOR] Test #18 "On delete error, confirmation panel stays open with error message" — the plan shows `_deletingId` stays set, but no `_deleteError` signal is defined in the architecture (Section 3.1). A `_deleteError: signal<string | null>` needs to be added to `UploadHistoryComponent` for this test to be implementable as specified. Add to Section 3.1 architecture.

---

### Required Changes Before Implementation Begins

1. **Fix `PnlSummary` model alignment**: Update `core/models/pnl.model.ts`:
   - Change `PnlPeriodEntry` to `{period_label, options_pnl, equity_pnl, total_pnl}` (correctly identified in plan)
   - Rename `PnlSummary.entries` → `items`
   - Remove `total_realized_pnl` from interface (derive client-side if needed in template)
   - Update `pnl.service.ts` to accept `underlying` in params
   - Update all `PnlService` specs that use the old `PnlSummary` mock shape

2. **Fix `Upload` model to use `uploaded_at`**: Coordinate with the F-15 post-F-12 model update. Update mock fixtures in plan spec references.

3. **Fix `UploadService.getUploads()` pagination handling**: Update service to correctly handle `UploadListResponse`.

4. **Add `_deleteError: signal<string | null>` to `UploadHistoryComponent` architecture** (Section 3.1) to support test #18.

5. **Update plan references**: Everywhere `_summary()?.entries` appears, change to `_summary()?.items`; everywhere `upload.created_at` appears for the Uploaded column, change to `upload.uploaded_at`.

---

### Next Steps

The model fixes (items 1–3) should be done as a single coordinated model-alignment commit before any component implementation begins. Once the models and service are corrected, the TDD implementation order in Section 6 is appropriate: model update first, then `UploadHistoryComponent`, then `PnlSummaryComponent`, then full quality gate.

F-18 may begin implementation once these conditions are resolved — no architectural rework is needed, only model alignment.
