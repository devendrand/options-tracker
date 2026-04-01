---

## IMPLEMENTATION REVIEW: F-14 — Angular Core Services

**Reviewer:** tech-lead-architect
**Date:** 2026-03-31
**Files reviewed:**
- `frontend/src/app/core/api.config.ts` + spec
- `frontend/src/app/core/interceptors/error.interceptor.ts` + spec
- `frontend/src/app/core/services/upload.service.ts` + spec
- `frontend/src/app/core/services/transaction.service.ts` + spec
- `frontend/src/app/core/services/position.service.ts` + spec
- `frontend/src/app/core/services/pnl.service.ts` + spec
- `frontend/src/app/core/models/*.model.ts`

---

### VERDICT: APPROVED WITH CONDITIONS

---

### Requirements Compliance: PASS

All CLAUDE.md API endpoints are implemented:

| Endpoint | Service | Implemented |
|---|---|---|
| `POST /api/v1/uploads` | `UploadService.createUpload()` | YES — multipart FormData |
| `GET /api/v1/uploads` | `UploadService.getUploads()` | YES |
| `GET /api/v1/uploads/{id}` | `UploadService.getUpload(id)` | YES |
| `DELETE /api/v1/uploads/{id}` | `UploadService.deleteUpload(id)` | YES |
| `GET /api/v1/transactions` | `TransactionService.getTransactions()` | YES |
| `GET /api/v1/positions` | `PositionService.getPositions()` | YES |
| `GET /api/v1/positions/{id}` | `PositionService.getPosition(id)` | YES |
| `GET /api/v1/pnl/summary` | `PnlService.getSummary()` | YES |

One endpoint from CLAUDE.md is not covered by a service method:
- `GET /api/v1/uploads/{id}` — present, but there is no corresponding upload detail endpoint that the specs test for upload detail page (not a blocker for this layer, but F-18 will need it).

All pagination parameters (`offset`, `limit`, max 500) are passable via query params. Filterable params per service are correct.

---

### Code Coverage: PASS

- Reported Coverage: 100% across all 14 test suites, 44 tests (verified by CI gate output)
- Threshold: 100% (project-mandated)
- All service methods, all query param branches (including `undefined` omission), and all interceptor error paths covered.

---

### Architectural Alignment: PASS

- All services use `inject()` (not constructor DI), consistent with Angular 17+ standalone component patterns and the plan's architecture decisions.
- `API_BASE_URL` `InjectionToken` with factory default is a clean, testable approach — avoids hardcoded strings in services and allows test overrides without environment file manipulation.
- `HttpInterceptorFn` functional interceptor pattern used correctly for `errorInterceptor`.
- `provideHttpClient(withInterceptors([...]))` is the correct modern Angular pattern.
- `HttpParams` built with explicit `undefined` guards — no accidental empty-string params.
- Standalone, pure model interfaces — no class decorators on models, appropriate for DTOs.
- `PaginatedResponse<T>` generic is reused correctly across Transaction and Position services.

---

### Code Quality: PASS

- Naming is consistent with backend schema snake_case fields throughout model interfaces.
- `TransactionCategory` union type mirrors CLAUDE.md classification table exactly — all 15 categories present.
- `UploadStatus` union type covers `PENDING | PROCESSING | COMPLETED | FAILED | SOFT_DELETED`.
- `PositionStatus` covers `OPEN | CLOSED | PARTIALLY_CLOSED`.
- Numeric fields from backend (price, amount, commission, quantity) correctly typed as `string` to avoid floating-point precision loss — good practice for financial data.
- `realized_pnl: string | null` on `OptionsPosition` correctly handles open positions.
- Test fixtures use realistic domain values (correct date formats, realistic amounts, valid category strings).

---

### Issues Found

- [MAJOR] `errorInterceptor` does not extract the FastAPI `detail` field from the response body. The plan spec (Section 5) requires: `Maps to ApiError { status: response.status, message: ... } (extracts detail from FastAPI JSON body when present)`. The current implementation re-throws the raw `HttpErrorResponse` unchanged. This means consumers receive an opaque Angular error object rather than a structured `ApiError`. The 422 test in the spec asserts only `err` is truthy — it does not verify the `detail` array is accessible. This is a deviation from the approved plan. It does not block F-14 approval since the interceptor still propagates errors correctly and no feature component currently depends on `ApiError` shape, but it must be resolved before F-15 (Upload UI) is implemented, as upload error display requires reading the `detail` field.

- [MAJOR] `LoadingInterceptor` is absent. The approved plan (Section 5, Section 10 steps 1–2) required `loading.interceptor.ts`, `loading.service.ts`, and their specs. These are not present in the reviewed files. If they exist elsewhere in the codebase this finding is voided — but they were not in the file listing provided for review.

- [MINOR] CI pins Node 20 (`frontend-ci.yml` line 30: `node-version: "20"`). This is correct and intentional — see Node.js version issue section below. No action needed on the CI file itself.

- [MINOR] `api.config.ts` exports `provideApiConfig()` as an `EnvironmentProviders` factory but the plan specified environment files (`environment.ts` / `environment.prod.ts`) for API URL config. The `InjectionToken` approach is architecturally superior and more testable — this deviation is approved. However, the `app.config.ts` bootstrap wiring for this token is not visible in the reviewed files and should be confirmed in F-03 scaffold review.

---

### Required Changes Before Approval

1. Before F-15 implementation begins: implement `ApiError { status: number; message: string; detail?: unknown }` model and update `errorInterceptor` to extract `error.error?.detail ?? error.message` into `ApiError`. Update the interceptor spec to assert the structured type is re-thrown, not just that `err` is truthy. Specifically, the 422 test must assert the `detail` array is accessible on the thrown error.

2. Confirm whether `LoadingInterceptor` and `LoadingService` were implemented as part of F-03 scaffold or are genuinely missing. If missing, these must be added before F-15. The spinner component in the shared module depends on `LoadingService`.

---

### Node.js Version Issue

**Finding:** The local development environment is running Node.js **v25.8.2**. This is a current-release (odd-numbered) version, not an LTS release. Angular 21 and its build toolchain (`@angular/build`, `esbuild`) have known instability on Node v25 — the frontend-dev agent reported `ng build --configuration production` crashing with exit code 134, which is consistent with memory allocation or V8 API incompatibilities in pre-LTS Node releases.

**CI configuration:** `frontend-ci.yml` correctly pins `node-version: "20"` (Node 20 LTS). Builds in CI will succeed. The crash is a local developer environment issue only.

**No `.nvmrc` file exists** in `frontend/`. This means any developer who does not manually manage their Node version will hit this crash on Node v25.

**No `engines` field** in `frontend/package.json` — Node version is not constrained at the package level.

**Recommendation:** Create `frontend/.nvmrc` with content `22` (Node 22 LTS, current active LTS as of 2026). This gives developers with `nvm` a one-command fix (`nvm use`) and signals the supported version clearly. Alternatively update to `node-version: "22"` in CI to align with the LTS that will still be in active support during v0.1 development.

**Action required:** Create `frontend/.nvmrc`. This is a [MINOR] configuration fix but should be done immediately to unblock any developer hitting the exit-134 crash.

---

### Next Steps

1. Create `frontend/.nvmrc` with `22` immediately (unblocks local `ng build` crashes).
2. Resolve the two MAJOR findings (ApiError shape, LoadingInterceptor presence) before F-15 implementation begins.
3. F-15 (Upload UI), F-16, F-17, F-18 may proceed in parallel for everything except the upload error display path, which depends on item 2.

---
---

## PLAN REVIEW: F-14 — Angular Core Services + HTTP Client Setup

**Reviewer:** tech-lead-architect  
**Date:** 2026-03-30  
**Plan file:** `.team/features/F-14-angular-core-services/plan/plan.md`

---

### VERDICT: ❌ REJECTED

---

### Summary

The plan filed under `F-14-angular-core-services` is **byte-for-byte identical** to the F9 plan previously reviewed at `.team/features/F9-frontend-core/plan/plan.md`. It has not incorporated either of the two required changes from that review. The document header still reads "F9: Frontend Core" with `Status: Draft (awaiting TechLead approval)`. This is not an updated F-14 plan — it is the unmodified F9 draft re-filed in a different directory.

---

### Rejection Reasons

#### 1. Previous review conditions still unaddressed

My F9 review (`.team/features/F9-frontend-core/plan/review.md`, 2026-03-30) required two changes before proceeding. Neither has been resolved:

**Required change 1 — Missing P&L Summary route stub:**  
Section 6 still lists only 5 routes. F-18 (P&L Summary page) requires a sixth route. Must add:
- `/pnl-summary` → lazy `PnlSummaryComponent` to `app.routes.ts`
- `PnlSummaryComponent` stub + smoke-test spec to the feature stubs table (Section 2)
- Section 10 step 10 (`AppComponent` TDD) must assert nav links for all **6** routes

**Required change 2 — `RelativeDatePipe` timezone handling unspecified:**  
Section 10 step 9 still reads "`RelativeDatePipe` — ISO string → formatted date" with no timezone constraint. PRD domain values are `YYYY-MM-DD` strings. Parsing with native `new Date('2026-03-15')` shifts the date by ±1 day in non-UTC browser environments. The spec must mandate Angular `DatePipe` with `'UTC'` timezone and include this concrete test:
```typescript
expect(pipe.transform('2026-03-15')).toBe('Mar 15, 2026'); // must pass in any timezone
```

#### 2. `@angular/cdk` still missing from dependencies

Previously flagged as minor; now a required fix. F-17 (Positions Page) needs an expandable drawer — `@angular/cdk/expansion` or `@angular/cdk/overlay` is the correct implementation. Add `@angular/cdk` to `package.json` at scaffold time.

#### 3. Plan identity incorrect

The header title is "F9: Frontend Core" not "F-14: Angular Core Services". If the intention is to combine F-03 (Frontend Scaffold) + F-14 (Angular Core Services) into one plan, the document must say so explicitly and must satisfy all acceptance criteria for both backlog items. Right now it does neither.

---

### Required Changes Before Re-submission

1. Update plan title/header to correctly identify scope (F-14, or explicitly "F-03 + F-14 combined").
2. Add `/pnl-summary` route stub with `PnlSummaryComponent` stub + spec.
3. Update `AppComponent` TDD step to assert all 6 nav routes.
4. Specify `RelativeDatePipe` uses Angular `DatePipe` with `'UTC'`; add the timezone edge-case test to Section 10 step 9.
5. Add `@angular/cdk` to `package.json` dependencies.

---

### Next Steps

Address all 5 items above, update the plan document, and re-submit for review. Implementation must not begin until this plan is approved. F-15, F-16, F-17, and F-18 are all blocked on this plan being correct and its implementation completing the quality gate.
