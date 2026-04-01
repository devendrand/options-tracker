## PLAN REVIEW: F-17 — Positions Page + Dashboard

**Reviewer:** tech-lead-architect
**Date:** 2026-04-01
**Plan file:** `.team/features/F-17-positions-dashboard/plan/plan.md`

---

### VERDICT: ❌ REJECTED

---

### Summary

The F-17 plan has three critical backend API contract mismatches that will cause runtime failures in the `PositionDrawerComponent` and `DashboardComponent`. These are not plan-level ambiguities — they are factual inconsistencies between the plan's assumed API shapes and the actual backend schemas in `backend/app/schemas/position.py` and `backend/app/schemas/pnl.py`. The plan must be corrected before implementation begins.

---

### Requirements Compliance: ⚠️ PARTIAL

OQ1 (combined P&L on dashboard) and OQ2 (expandable drawer) are correctly addressed architecturally. However, the drawer content specified in Section 5.3 cannot be rendered as written because the required leg fields do not exist in the backend response.

---

### API Contract Alignment: ❌ FAIL

#### Critical Issue 1 — `OptionsPositionLegResponse` is missing required fields

The plan's drawer (Section 5.3) displays per-leg `price`, `amount`, `commission`, and `trade_date`. However, the actual backend schema at `backend/app/schemas/position.py` is:

```python
class OptionsPositionLegResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    leg_role: LegRole
    quantity: Decimal
```

Only `id`, `transaction_id`, `leg_role`, and `quantity` are returned. `price`, `amount`, `commission`, and `trade_date` are **absent**. The drawer as specified will display blank/undefined values for 4 of its 6 columns. The per-pair P&L formula `open.amount + close.amount − |open.commission| − |close.commission|` also cannot be computed without `amount` and `commission`.

**Resolution required before implementation:**  
Either (a) extend `OptionsPositionLegResponse` in the backend to include `price`, `amount`, `commission`, `trade_date` — coordinate with backend-tdd-api-dev, or (b) revise the drawer to only display fields the backend actually returns (`leg_role`, `quantity`) and remove the P&L formula until the backend schema is extended.

#### Critical Issue 2 — `leg_role` vs `leg_type` naming mismatch

The backend response field is `leg_role` (per `OptionsPositionLegResponse`), but the frontend `OptionsPositionLeg` model uses `leg_type`. The plan's drawer references `leg.leg_type` throughout (Section 5.3, tests 6–7). At runtime, `leg.leg_type` will be `undefined` because the backend sends `leg_role`.

**Resolution required:** Update `OptionsPositionLeg` in `position.model.ts` to use `leg_role` instead of `leg_type`, or add a mapping layer in `PositionService.getPosition()`.

#### Critical Issue 3 — `PnlSummaryResponse` has no `total_realized_pnl` field

The dashboard (Section 3.2) calls `pnlService.getSummary({ period: 'year' })` and reads `summary.total_realized_pnl` to populate the P&L card. However, the actual backend schema at `backend/app/schemas/pnl.py` is:

```python
class PnlSummaryResponse(BaseModel):
    period: str
    items: list[PnlPeriodResponse]
```

There is no `total_realized_pnl` field. The P&L card will always show `undefined`. Additionally:
- The backend uses `items` but the frontend `PnlSummary` interface uses `entries`
- The frontend `PnlSummary` shape (`total_realized_pnl`, `period: PnlPeriod | null`, `entries`) does not match the backend response at all

**Resolution required:** Either (a) add `total_realized_pnl` to `PnlSummaryResponse` on the backend — coordinate with backend-tdd-api-dev — or (b) compute total P&L client-side by summing `items[].total_pnl` after the F-18 model update. Update the `PnlSummary` frontend interface to align with the actual backend shape: rename `entries` → `items` and either add or remove `total_realized_pnl`.

---

### Additional Issues Found

- [MAJOR] **`PositionListResponse` shape mismatch.** The backend returns `{total, offset, limit, options_items, equity_items}` but `PositionService.getPositions()` is typed as `PaginatedResponse<OptionsPosition>` (which has `items`). The service `getPositions()` response will not have a `.items` field at runtime — it will have `.options_items` and `.equity_items`. The `PositionsComponent` reads `response.items` which will be `undefined`. This is a pre-existing F-14 service issue, but the F-17 plan must account for it. Options: (a) fix `PositionService` to return a typed `PositionListResponse`; (b) use `.pipe(map(r => r.options_items))` in the service.

- [MAJOR] **Frontend `OptionsPosition` model missing fields from backend.** The backend `OptionsPositionResponse` includes `direction: PositionDirection` and `option_symbol: str` which are absent from the frontend model. While not blocking F-17's table columns (the plan doesn't display them), the model mismatch should be corrected before implementation so the model is accurate.

- [MINOR] The `PositionDrawerComponent` uses `@Input() positionId!: string`. In Angular 21 with signals, `input()` signal is preferred over the decorator-based `@Input()`. Not a blocker, but align with the project's modern Angular patterns.

- [MINOR] Test #14 (Section 6.3) "Two drawers can be open simultaneously" — this test requires careful setup (two `toggleDrawer()` calls, then verifying both `PositionDrawerComponent` instances are in the DOM). The test description is correct but the implementation will need a `Set.prototype.has` or spread clone to avoid mutating the signal set directly. The plan should note: `_expandedIds` must be updated immutably (`new Set([...set, id])` on add, `new Set([...set].filter(i => i !== id))` on remove) since Angular signal change detection requires a new reference.

---

### Required Changes Before Re-submission

1. **Resolve leg schema gap** (Critical Issue 1): Coordinate with backend-tdd-api-dev to extend `OptionsPositionLegResponse` to include `price`, `amount`, `commission`, `trade_date` — OR revise the drawer spec to only display `leg_role` and `quantity` with a note that P&L per-pair display is deferred until backend schema is extended.

2. **Fix `leg_type` → `leg_role`** (Critical Issue 2): Update `position.model.ts` `OptionsPositionLeg` to use `leg_role: 'OPEN' | 'CLOSE'` and update all plan references accordingly.

3. **Resolve `total_realized_pnl`** (Critical Issue 3): Align `PnlSummary` interface with actual `PnlSummaryResponse` — rename `entries` → `items`, confirm whether `total_realized_pnl` is added to the backend or derived client-side.

4. **Fix `PositionService` response shape**: Address `options_items` vs `items` mismatch so `PositionsComponent` can read the position list correctly.

5. **Update `OptionsPosition` model**: Add `direction` and `option_symbol` fields from `OptionsPositionResponse`.

6. **Confirm `@angular/cdk` is installed**: The F-14 review required `@angular/cdk` to be added to `package.json`. Verify it is present before wiring up any CDK expansion if the revised plan opts for CDK — the current inline drawer approach does not require CDK, which is acceptable.

---

### Next Steps

1. Coordinate with backend-tdd-api-dev on leg schema extension (item 1) and `total_realized_pnl` (item 3) — these require backend schema changes that affect F-13 and F-17 simultaneously.
2. Update `position.model.ts` and `pnl.model.ts` to match actual backend schemas.
3. Revise the F-17 plan to reflect the corrected API shapes and re-submit for review.
4. Implementation must not begin until the revised plan is approved.
