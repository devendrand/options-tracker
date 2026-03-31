# F-03: Frontend Project Scaffold — Implementation Plan

**Feature:** F-03  
**Owner:** angular-tdd-frontend  
**Date:** 2026-03-30  
**Depends on:** F-01 (Docker Compose scaffold)

---

## 1. Goal

Bootstrap the `frontend/` Angular workspace with Jest (replacing Karma), ESLint + Prettier, lazy-loaded routing stubs for all 6 feature areas, environment configuration, and path aliases. All CI quality gates must pass on the empty scaffold: `npm ci` → `ng lint` → `prettier check` → `jest 100% coverage` → `ng build --configuration production`.

---

## 2. Files to Create / Modify

### Root config
- `package.json` — Angular 19 LTS + Jest + ESLint + Prettier + @angular/cdk
- `angular.json` — workspace, lint builder pointing to ESLint
- `tsconfig.json` — strict mode, path aliases `@core/*`, `@shared/*`, `@features/*`
- `tsconfig.app.json` — app build config
- `tsconfig.spec.json` — Jest-compatible spec config (no jasmine types)
- `jest.config.ts` — jest-preset-angular, 100% coverage threshold
- `.eslintrc.json` — @angular-eslint + prettier integration
- `.prettierrc` — singleQuote, trailingComma all, printWidth 100
- `.prettierignore`

### Source
- `src/main.ts`
- `src/index.html`
- `src/styles.scss`
- `src/environments/environment.ts` — `{ production: false, apiBaseUrl: 'http://localhost:8000' }`
- `src/environments/environment.prod.ts` — `{ production: true, apiBaseUrl: '/api' }`
- `src/app/app.config.ts` — provideRouter, provideHttpClient
- `src/app/app.routes.ts` — 6 lazy routes
- `src/app/app.component.ts` — standalone, OnPush
- `src/app/app.component.html`
- `src/app/app.component.spec.ts`

### Feature stubs (standalone components, OnPush)
Each feature gets a `component.ts` + `component.html` + `component.spec.ts`:
- `src/app/features/dashboard/dashboard.component.*`
- `src/app/features/upload/upload.component.*`
- `src/app/features/transactions/transactions.component.*`
- `src/app/features/positions/positions.component.*`
- `src/app/features/upload-history/upload-history.component.*`
- `src/app/features/pnl-summary/pnl-summary.component.*` ← tech lead required

### Shared pipes
- `src/app/shared/pipes/relative-date.pipe.ts` — uses Angular `DatePipe` with `'UTC'` timezone
- `src/app/shared/pipes/relative-date.pipe.spec.ts` — includes UTC timezone edge case test

### Core stubs (empty placeholder files for F-14)
- `src/app/core/.gitkeep`
- `src/app/shared/.gitkeep`

---

## 3. Architectural Decisions

| Decision | Rationale |
|---|---|
| Standalone components (no NgModules) | Angular 17+ default; no module boilerplate |
| OnPush change detection | Performance default; explicit push model |
| Functional HTTP interceptors | Angular 15+ best practice |
| Lazy `loadComponent` routing | Code-splitting without feature modules |
| Jest + jest-preset-angular | Faster than Karma; CLAUDE.md mandated |
| Angular DatePipe('UTC') in RelativeDatePipe | Avoids ±1 day timezone shift on YYYY-MM-DD strings |
| @angular/cdk included from day 1 | Required for positions drawer overlay in F-17 |

---

## 4. Routing Skeleton

```
/              → redirect to /dashboard
/dashboard     → DashboardComponent (lazy)
/upload        → UploadComponent (lazy)
/transactions  → TransactionsComponent (lazy)
/positions     → PositionsComponent (lazy)
/upload-history→ UploadHistoryComponent (lazy)
/pnl-summary   → PnlSummaryComponent (lazy)   ← tech lead required
**             → redirect to /dashboard
```

---

## 5. TDD Order (Red → Green → Refactor)

1. `RelativeDatePipe` — write spec first:
   - `2026-03-15` renders as `Mar 15, 2026`
   - UTC midnight edge case: `2026-03-15T00:00:00Z` renders as `Mar 15, 2026` (not Mar 14)
   - Then implement using `DatePipe` with `'UTC'`
2. `AppComponent` — write spec first:
   - Renders `<router-outlet>`
   - Component title is `'options-tracker-ui'`
   - Then implement minimal component
3. Feature stub components — write minimal spec (creates component) then implement
4. Run `jest --coverage` to verify 100% threshold passes

---

## 6. Coverage Strategy

All generated stubs include a `*.spec.ts` that at minimum:
- Creates the component via `TestBed`
- Asserts it is truthy
- Covers all branches in `RelativeDatePipe.transform()`

This satisfies the 100% line + branch + function + statement threshold.

---

## 7. Quality Gate Commands

```bash
cd frontend/
npm ci
npx ng lint
npx prettier --check "src/**/*.{ts,html,scss}"
npx jest --coverage
npx ng build --configuration production
```

All must pass before F-03 is marked complete.
