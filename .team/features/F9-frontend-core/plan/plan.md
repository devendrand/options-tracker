# F9: Frontend Core — Angular Scaffold, Routing, ApiService, Shared Components

**Feature:** F9  
**Owner:** angular-tdd-frontend  
**Status:** Draft (awaiting TechLead approval)  
**Depends on:** F1 (Docker/CI scaffolding complete, project root structure in place)

---

## 1. Objectives

Bootstrap the Angular workspace that all feature modules (F10–F14) build on:

- Angular latest LTS workspace, strict TypeScript
- Jest + jest-preset-angular at 100% coverage gate (replacing Karma)
- ESLint + @angular-eslint + Prettier configured
- Core module: `ApiService`, error HTTP interceptor, loading HTTP interceptor
- Environment-based API URL config (`http://localhost:8000` dev, `/api` prod)
- App routing module skeleton with lazy-loaded feature route stubs
- Shared module: reusable components and pipes used across features
- `frontend/Dockerfile` + wiring in `docker-compose.yml`
- `frontend-ci.yml` GitHub Actions pipeline

---

## 2. Scope

### 2.1 Files to create / configure

#### Workspace config
| File | Purpose |
|---|---|
| `frontend/package.json` | Angular LTS, Jest, jest-preset-angular, ESLint, Prettier deps |
| `frontend/angular.json` | Workspace — Jest builder, SCSS, strict mode |
| `frontend/tsconfig.json` | `strict: true`, path aliases (`@core`, `@shared`, `@features`) |
| `frontend/tsconfig.spec.json` | Jest TS config (`esModuleInterop`, `emitDecoratorMetadata`) |
| `frontend/jest.config.ts` | `jest-preset-angular` preset, `collectCoverageFrom`, `coverageThreshold: 100` |
| `frontend/.eslintrc.json` | `@angular-eslint` + `eslint-plugin-prettier` |
| `frontend/.prettierrc` | `singleQuote: true`, `trailingComma: 'all'`, `printWidth: 100` |

#### Environments
| File | Purpose |
|---|---|
| `frontend/src/environments/environment.ts` | `{ production: false, apiBaseUrl: 'http://localhost:8000' }` |
| `frontend/src/environments/environment.prod.ts` | `{ production: true, apiBaseUrl: '/api' }` |

#### App bootstrap
| File | Purpose |
|---|---|
| `frontend/src/main.ts` | `bootstrapApplication(AppComponent, appConfig)` |
| `frontend/src/app/app.config.ts` | `provideRouter`, `provideHttpClient(withInterceptors([...]))`, `provideAnimations` |
| `frontend/src/app/app.routes.ts` | Lazy-loaded routes for all 5 feature areas |
| `frontend/src/app/app.component.ts` | Root shell (nav + `<router-outlet>`) |
| `frontend/src/app/app.component.html` | Navigation bar + `<router-outlet>` |
| `frontend/src/app/app.component.spec.ts` | Unit tests |

#### Core module (`src/app/core/`)
| File | Purpose |
|---|---|
| `api.service.ts` | Typed `HttpClient` wrapper — `get`, `post`, `delete` |
| `api.service.spec.ts` | Unit tests — `HttpClientTestingModule` + `HttpTestingController` |
| `interceptors/error.interceptor.ts` | Maps HTTP 4xx/5xx → typed `ApiError`; re-throws |
| `interceptors/error.interceptor.spec.ts` | Unit tests — intercept 400/404/422/500 + network errors |
| `interceptors/loading.interceptor.ts` | Increments/decrements `LoadingService` counter per in-flight request |
| `interceptors/loading.interceptor.spec.ts` | Unit tests |
| `loading.service.ts` | `isLoading$: Observable<boolean>` (BehaviorSubject-backed counter) |
| `loading.service.spec.ts` | Unit tests |
| `models/api-error.model.ts` | `ApiError { status: number; message: string }` |

#### Shared module (`src/app/shared/`)
| File | Purpose |
|---|---|
| `components/loading-spinner/loading-spinner.component.ts` | Reusable centred spinner, `@Input() message` |
| `components/loading-spinner/loading-spinner.component.spec.ts` | Unit tests |
| `components/error-alert/error-alert.component.ts` | Dismissible error banner, `@Input() error`, `@Output() dismissed` |
| `components/error-alert/error-alert.component.spec.ts` | Unit tests |
| `components/status-badge/status-badge.component.ts` | Colour-coded status chip (`OPEN`, `CLOSED`, `DUPLICATE`, etc.) |
| `components/status-badge/status-badge.component.spec.ts` | Unit tests |
| `pipes/category-label.pipe.ts` | Formats internal `category` enum → human-readable label |
| `pipes/category-label.pipe.spec.ts` | Unit tests — all category values |
| `pipes/relative-date.pipe.ts` | Formats ISO date string → `MMM d, yyyy` |
| `pipes/relative-date.pipe.spec.ts` | Unit tests |

#### Feature stubs (`src/app/features/`)
Each stub has one component file + one spec with a single "creates" smoke test:

| Feature | Route | Stub component |
|---|---|---|
| Dashboard | `/dashboard` | `DashboardComponent` |
| Upload | `/upload` | `UploadComponent` |
| Transactions | `/transactions` | `TransactionsComponent` |
| Positions | `/positions` | `PositionsComponent` |
| Upload History | `/uploads` | `UploadHistoryComponent` |

#### Docker
| File | Purpose |
|---|---|
| `frontend/Dockerfile` | Multi-stage: `ng build --configuration production` → nginx:alpine serve |
| `frontend/nginx.conf` | `try_files $uri $uri/ /index.html` for Angular routing |

#### CI
| File | Purpose |
|---|---|
| `.github/workflows/frontend-ci.yml` | npm ci → ng lint → prettier check → jest 100% → ng build production |

---

## 3. Angular Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Component style | **Standalone components** | Angular 17+ default; no NgModules overhead |
| Change detection | **OnPush** | Performance default on all new components |
| HTTP interceptors | **Functional interceptors** (`HttpInterceptorFn`) | Preferred in Angular 15+; works with `provideHttpClient(withInterceptors([...]))` |
| State management | **Services + RxJS BehaviorSubject** | v0.1 scope; NgRx is over-engineering here |
| Routing | **Lazy `loadComponent`** | Code-split per feature; no feature modules needed |
| CSS | **SCSS** | Angular scaffold default; enables nesting and variables |
| Test runner | **Jest** (`jest-preset-angular`) | Faster than Karma; jsdom; CI-compatible headless |

---

## 4. ApiService Interface

```typescript
// core/api.service.ts
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly base = environment.apiBaseUrl;
  constructor(private http: HttpClient) {}

  get<T>(path: string, params?: Record<string, string | number>): Observable<T>
  post<T>(path: string, body: unknown): Observable<T>
  postFormData<T>(path: string, formData: FormData): Observable<T>
  delete<T>(path: string): Observable<T>
}
```

- `postFormData` needed for F10 (multipart CSV upload via `POST /api/v1/uploads`).
- No error handling in `ApiService` itself — that is the `ErrorInterceptor`'s responsibility.
- Unit tests use `HttpClientTestingModule` + `HttpTestingController`.

---

## 5. Interceptors

### ErrorInterceptor
- Intercepts any `HttpErrorResponse`.
- Maps to `ApiError { status: response.status, message: ... }` (extracts `detail` from FastAPI JSON body when present).
- Re-throws via `throwError(() => apiError)`.
- Handles network errors (status = 0).

### LoadingInterceptor
- On request start: call `loadingService.increment()`.
- On response/error finalize: call `loadingService.decrement()`.
- `LoadingService.isLoading$` emits `true` when counter > 0.

---

## 6. Routing Structure

```
/                     → redirectTo: '/dashboard'
/dashboard            → lazy DashboardComponent
/upload               → lazy UploadComponent
/transactions         → lazy TransactionsComponent
/positions            → lazy PositionsComponent
/uploads              → lazy UploadHistoryComponent
**                    → redirectTo: '/dashboard'
```

---

## 7. Shared Components

### LoadingSpinnerComponent
- `@Input() message: string = 'Loading...'`
- Standalone, OnPush
- Centred spinner element + message text

### ErrorAlertComponent
- `@Input() error: string | null = null`
- `@Output() dismissed = new EventEmitter<void>()`
- Not rendered when `error` is null (via `@if`)
- Standalone, OnPush

### StatusBadgeComponent
- `@Input() status!: string`
- Maps status strings to CSS classes: `open` (blue), `closed` (green), `duplicate` (amber), `parse_error` (red), etc.
- Standalone, OnPush

### CategoryLabelPipe
- Transform: internal category string → human-readable label
- e.g. `'OPTIONS_SELL_TO_OPEN'` → `'Sell to Open'`
- Pure pipe

### RelativeDatePipe
- Transform: ISO date string → `MMM d, yyyy` (e.g. `'Mar 15, 2026'`)
- Pure pipe

---

## 8. Docker

### `frontend/Dockerfile`

```dockerfile
# Stage 1: build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npx ng build --configuration production

# Stage 2: serve
FROM nginx:alpine
COPY --from=builder /app/dist/options-tracker/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### `frontend/nginx.conf`
```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;
  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

### `docker-compose.yml` additions
```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  ports:
    - "4200:80"
  depends_on:
    - backend
```

---

## 9. CI — `frontend-ci.yml`

```yaml
name: Frontend CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  build-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npx ng lint
      - run: npx prettier --check .
      - run: npx jest --coverage --ci
      - run: npx ng build --configuration production
```

---

## 10. TDD Plan (Red → Green → Refactor)

Tests are written **before** implementation in this exact order:

1. **`LoadingService`** — `isLoading$` starts false; increments to true; back to false after decrement
2. **`LoadingInterceptor`** — increments on request, decrements on complete, decrements on error
3. **`ErrorInterceptor`** — 400/404/422/500 → `ApiError`; network error (status=0) → `ApiError`; extracts FastAPI `detail` field
4. **`ApiService`** — `get` correct URL + params; `post` correct URL + body; `postFormData` correct multipart; `delete` correct URL
5. **`LoadingSpinnerComponent`** — renders message; custom message; spinner element present
6. **`ErrorAlertComponent`** — hidden when null; shows message; dismiss click emits event
7. **`StatusBadgeComponent`** — correct CSS class per status string
8. **`CategoryLabelPipe`** — each known category value → expected label; unknown → passthrough
9. **`RelativeDatePipe`** — ISO string → formatted date
10. **`AppComponent`** — `<router-outlet>` present; nav links for all 5 routes
11. **Feature stub specs** — each creates without error (one test per stub)

---

## 11. Quality Gates

All must pass before F9 is declared complete:

```bash
cd frontend
npx ng lint                              # ESLint clean
npx prettier --check .                   # Formatting clean
npx jest --coverage --ci                 # 100% lines, branches, functions, statements
npx ng build --configuration production  # Production build succeeds
```

---

## 12. Implementation Order

1. `package.json` + install
2. `angular.json`, `tsconfig.json`, `tsconfig.spec.json`
3. `jest.config.ts`
4. `.eslintrc.json`, `.prettierrc`
5. `environments/`
6. **TDD: `LoadingService` → `LoadingInterceptor` → `ErrorInterceptor` → `ApiService`**
7. **TDD: `LoadingSpinnerComponent` → `ErrorAlertComponent` → `StatusBadgeComponent`**
8. **TDD: `CategoryLabelPipe` → `RelativeDatePipe`**
9. **TDD: `AppComponent` shell + routing**
10. Feature stub components (each with smoke test)
11. `Dockerfile` + `nginx.conf`
12. `frontend-ci.yml`
13. Full quality gate pass

---

## 13. Dependencies / Blockers

- **F1 must be complete** before implementation — Docker Compose root structure and `ng new` scaffold must exist
- No backend API dependency for F9 — `ApiService` tested with mocks only
- F10–F14 all depend on F9 completing first
