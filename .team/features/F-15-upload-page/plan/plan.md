# F-15: Upload Page

**Feature:** F-15  
**Owner:** angular-tdd-frontend  
**Status:** Substantially implemented — plan documents as-built state and remaining gaps  
**Depends on:** F-14 (Angular Core Services), F-12 (Upload API — for model alignment on completion)

---

## 1. Objectives

Implement the CSV Upload page at `/upload` so users can:

1. Select or drag-and-drop an E\*TRADE CSV file
2. Trigger the upload to `POST /api/v1/uploads` via `UploadService.createUpload()`
3. See a loading indicator while the request is in-flight
4. See a result summary (filename, row count, options count, duplicates, parse errors) on success
5. See an error message with a retry option on failure
6. Reset back to the file-selection state via "Upload Another" or "Try Again"

---

## 2. Implementation Status

The `UploadComponent` at `frontend/src/app/features/upload/` is **already fully implemented** with tests. This plan documents the as-built design so the tech-lead can review it, and flags one pending model-alignment task tied to F-12.

---

## 3. Scope

### 3.1 Files (already created)

| File | Status | Purpose |
|---|---|---|
| `features/upload/upload.component.ts` | Done | Component logic — signals, upload flow |
| `features/upload/upload.component.html` | Done | Template — upload zone, loading, result, error states |
| `features/upload/upload.component.spec.ts` | Done | 30+ Jest assertions; 100% coverage |

### 3.2 Files pending (on F-12 completion)

| File | Action | Reason |
|---|---|---|
| `core/models/upload.model.ts` | Add fields | Add `possible_duplicate_count` and `internal_transfer_count` once F-12 backend ships these fields |
| `features/upload/upload.component.html` | Extend result block | Display `possible_duplicate_count` and `internal_transfer_count` in the result summary |
| `features/upload/upload.component.spec.ts` | Add assertions | Test the two new fields render in `[data-testid="result-state"]` |

---

## 4. Component Architecture

```
UploadComponent (standalone, OnPush)
  ├── inject(UploadService)          — createUpload(file): Observable<Upload>
  ├── _selectedFile: signal<File | null>
  ├── _isUploading: signal<boolean>
  ├── _uploadResult: signal<Upload | null>
  └── _errorMessage: signal<string | null>
```

No child components — the upload page is intentionally self-contained. `LoadingService` is **not** wired here; the `LoadingInterceptor` handles global loading, but the local `_isUploading` signal drives the page-local UI state (the template conditionally renders one of four states).

---

## 5. Template States (mutually exclusive `@if` blocks)

| Priority | State | Condition | `data-testid` |
|---|---|---|---|
| 1 | Loading | `isUploading` is true | `loading-state` |
| 2 | Result | `uploadResult` is non-null | `result-state` |
| 3 | Error | `errorMessage` is non-null | `error-state` |
| 4 (default) | Upload zone | none of the above | `upload-zone` |

---

## 6. User Flow

```
[Page load]
  → Upload Zone shown (file input + drag-drop target)
  → Upload button disabled until file selected

[File selected via input or drag-and-drop]
  → selectedFile set → Upload button enabled

[Upload button clicked]
  → isUploading = true → Loading state shown
  → uploadService.createUpload(file) called

  [Success]
    → uploadResult set, isUploading = false → Result state shown
    → "Upload Another" resets all state → Upload Zone shown

  [Error]
    → errorMessage set (from err.message ?? fallback), isUploading = false → Error state shown
    → "Try Again" resets all state → Upload Zone shown
```

---

## 7. Result Summary Fields

When `[data-testid="result-state"]` is displayed, show:

| Field | Source | Label |
|---|---|---|
| Filename | `uploadResult.filename` | "File:" |
| Row count | `uploadResult.row_count` | "Rows:" |
| Options count | `uploadResult.options_count` | "Options:" |
| Duplicate count | `uploadResult.duplicate_count` | "Duplicates:" |
| Parse error count | `uploadResult.parse_error_count` | "Errors:" |
| Possible duplicate count | `uploadResult.possible_duplicate_count` | "Possible duplicates:" ← add when F-12 ships |
| Internal transfer count | `uploadResult.internal_transfer_count` | "Internal transfers:" ← add when F-12 ships |

---

## 8. File Validation (client-side)

Client-side validation is intentionally minimal — the backend performs authoritative file-level validation per PRD §3.1.1. The component enforces:

- `<input type="file" accept=".csv">` — browser-level filter (advisory, not enforced)
- No size or format check client-side — backend rejects with HTTP 422 and the error message is surfaced in `[data-testid="error-state"]`

---

## 9. TDD Plan — Test Coverage (as-built)

Tests at `upload.component.spec.ts` cover these scenarios in order:

1. **Initial state** (6 tests)
   - Component creates without error
   - `selectedFile` is `null`
   - Upload button disabled when no file selected
   - Loading/result/error states are not rendered
   - File input has `accept=".csv"`

2. **File selection via input** (3 tests)
   - `selectedFile` set when `files[0]` present in `change` event
   - Upload button enabled after file selected
   - `selectedFile` stays `null` when files array is empty

3. **Drag and drop** (5 tests)
   - `selectedFile` set from `dataTransfer.files[0]`
   - `selectedFile` stays `null` when drop has no files
   - `selectedFile` stays `null` when `dataTransfer` is `null`
   - `dragover` calls `preventDefault()`
   - Upload zone element is rendered

4. **Upload success** (8 tests)
   - `isUploading` is `false` before calling `upload()`
   - Loading state visible while request is in-flight (Subject not yet resolved)
   - `uploadResult` set and `isUploading` cleared on `next`
   - Result state rendered; contains filename, row_count, options_count, duplicate_count, parse_error_count
   - "Upload Another" button present in result state

5. **Upload error** (4 tests)
   - `errorMessage` set and `isUploading` cleared on `error`
   - Error state rendered with error text
   - "Try Again" button present
   - Fallback message used when `err.message` is undefined

6. **reset()** (3 tests)
   - Clears `selectedFile`, `uploadResult`, `errorMessage`
   - Upload Zone rendered after reset from result state
   - Upload Zone rendered after reset from error state

7. **upload() guard** (1 test)
   - `uploadService.createUpload` not called when `selectedFile` is `null`

---

## 10. Quality Gates

```bash
cd frontend
npx ng lint                              # ESLint clean
npx prettier --check .                   # Formatting clean
npx jest --coverage --ci                 # 100% lines, branches, functions, statements
npx ng build --configuration production  # Production build succeeds
```

---

## 11. Implementation Order

The component is already implemented. The remaining work on F-15 is:

1. **When F-12 is merged:** update `Upload` interface in `core/models/upload.model.ts` to add `possible_duplicate_count: number | null` and `internal_transfer_count: number | null`
2. Extend `[data-testid="result-state"]` block in the template to show the two new fields
3. Add two assertions to `upload.component.spec.ts` for the new fields
4. Run quality gate — confirm 100% coverage maintained

---

## 12. Dependencies / Blockers

- **F-14 complete** — `UploadService` is already in place; component is wired correctly
- **F-12** — `Upload` model may gain `possible_duplicate_count` and `internal_transfer_count`; update F-15 after F-12 merges
- No routing change required — `/upload` route was pre-wired in F-14
