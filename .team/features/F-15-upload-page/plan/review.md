## IMPLEMENTATION REVIEW: F-15 — Upload Page

**Reviewer:** tech-lead-architect
**Date:** 2026-04-01
**Files reviewed:**
- `frontend/src/app/features/upload/upload.component.ts`
- `frontend/src/app/features/upload/upload.component.html` (verified via spec assertions)
- `frontend/src/app/features/upload/upload.component.spec.ts`
- `frontend/src/app/core/models/upload.model.ts`
- `frontend/src/app/core/services/upload.service.ts`
- `backend/app/schemas/upload.py`
- F-14 review at `.team/features/F-14-angular-core-services/plan/review.md`

---

### VERDICT: ✅ APPROVED WITH CONDITIONS

---

### Requirements Compliance: ✅ PASS

All 6 objectives are implemented and verified:
1. File selection via input and drag-and-drop — ✅ `onFileSelected`, `onDrop`, `onDragOver` implemented
2. Upload via `UploadService.createUpload()` — ✅ wired correctly
3. Loading indicator while request in-flight — ✅ `_isUploading` signal drives `[data-testid="loading-state"]`
4. Result summary on success — ✅ filename, row_count, options_count, duplicate_count, parse_error_count all shown
5. Error message with retry — ✅ `[data-testid="error-state"]` with fallback message
6. Reset via "Upload Another" / "Try Again" — ✅ `reset()` clears all state

---

### Code Coverage: ✅ PASS

- 31 Jest assertions across 7 describe blocks (one more than the plan's "30+" claim — correct)
- All branches covered: null file guard, drag with null dataTransfer, empty files array, fallback error message
- No coverage padding — each test asserts a meaningful condition

---

### Architectural Alignment: ✅ PASS

- Standalone component (Angular 21 default), `ChangeDetectionStrategy.OnPush`
- Uses `inject(UploadService)` — no constructor DI
- Four private signals (`_selectedFile`, `_isUploading`, `_uploadResult`, `_errorMessage`) with public getter/setter accessors — correct for OnPush test compatibility
- `LoadingInterceptor` and `ApiError` model confirmed present in `core/interceptors/` and `core/models/` — the two F-14 MAJOR findings are resolved
- No `@angular/cdk` dependency needed for this component — correct

---

### Code Quality: ✅ PASS

- Single responsibility: upload flow only, no routing or navigation logic
- Template state priority ordering (`isUploading` → `uploadResult` → `errorMessage` → default) is unambiguous and documented
- Error fallback message `'An unexpected error occurred.'` tested explicitly

---

### Issues Found

- [MAJOR] **Upload model is misaligned with the backend `UploadResponse` schema beyond what the plan documents.** The plan acknowledges `possible_duplicate_count` and `internal_transfer_count` need to be added post-F-12. However, there are three additional mismatches not flagged:
  1. Backend uses `uploaded_at: datetime`, frontend model has `created_at: string` and `updated_at: string`. Neither `created_at` nor `updated_at` exists in `UploadResponse`. At runtime, any code reading `upload.created_at` will get `undefined`.
  2. Backend `UploadResponse` has no `error_message` field. The frontend `Upload` interface includes it. This field will always be `undefined` when reading backend data.
  3. Backend counts (`row_count`, `options_count`, `duplicate_count`, `parse_error_count`) are non-nullable integers in `UploadResponse`. Frontend types them as `number | null`. While this won't break runtime, it is a type contract inaccuracy.

- [MAJOR] **`UploadService.getUploads()` is typed as `Observable<Upload[]>` but the backend endpoint `/api/v1/uploads` returns `UploadListResponse` (paginated: `{total, offset, limit, items}`), not a bare array.** This does not affect F-15 (which only calls `createUpload`), but it will cause runtime failures in F-18 (`UploadHistoryComponent`). The service layer must be corrected before F-18 implementation begins — either return `Observable<UploadListResponse>` and update the Upload History component accordingly, or add a `.pipe(map(r => r.items))` in the service. This issue should be documented explicitly in the F-18 plan.

- [MINOR] The `upload.component.ts` exposes `uploadResult` as a public setter (`set uploadResult(value)`). This is used in tests but is not needed in production code. No action required — it correctly enables the test setup patterns used in the spec.

---

### Required Changes Before Full F-15 Approval

1. **When F-12 is merged:** update `Upload` interface in `core/models/upload.model.ts` to:
   - Rename `created_at`/`updated_at` to `uploaded_at: string` (matching `UploadResponse.uploaded_at`)
   - Remove `error_message` (not in backend schema)
   - Add `possible_duplicate_count: number` and `internal_transfer_count: number` (non-nullable, per backend)
   - Make counts non-nullable: `row_count: number`, `options_count: number`, etc.
2. Update `upload.component.spec.ts` `mockUpload` fixture to match the corrected shape.
3. Extend template result block with the two new fields as planned.
4. Update `UploadService.getUploads()` return type and implementation to handle `UploadListResponse` pagination before F-18 starts.

---

### Next Steps

F-15 is approved — no further implementation work is required on the component until F-12 merges. The model alignment work in item 1 above should be done as part of the F-12 integration step already documented in the plan's Section 11. Ensure item 4 (service pagination fix) is included in that same pass.
