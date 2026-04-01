# F-04: GitHub Actions CI Pipelines — Implementation Plan

## Objective

Set up GitHub Actions CI workflows for backend, frontend, and Docker that enforce all quality gates
defined in CLAUDE.md. Pipelines must run on push and PR to `main` and `develop` branches.

---

## Workflows to Create

| File | Trigger Paths | Service Containers |
|---|---|---|
| `backend-ci.yml` | `backend/**` | PostgreSQL 16 |
| `frontend-ci.yml` | `frontend/**` | None |
| `docker-ci.yml` | push/PR to `main` only | None |

---

## Backend CI Pipeline (`backend-ci.yml`)

### Triggers
- `push` to `main`, `develop` — paths: `backend/**`
- `pull_request` to `main`, `develop` — paths: `backend/**`

### Steps
1. `actions/checkout@v4`
2. `actions/setup-python@v5` with Python 3.12
3. `snok/install-poetry@v1` — Poetry dependency manager
4. `poetry install` (working-directory: `backend/`)
5. `poetry run ruff check .` — lint
6. `poetry run ruff format --check .` — format check
7. `poetry run mypy app` — type checking
8. `poetry run pytest --cov=app --cov-fail-under=100 --cov-branch` — tests + coverage
9. `actions/upload-artifact@v4` — upload coverage report

### Service Container
- Image: `postgres:16`
- Env: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- Health check: `pg_isready` with retries
- DATABASE_URL injected as env var to test step

---

## Frontend CI Pipeline (`frontend-ci.yml`)

### Triggers
- `push` to `main`, `develop` — paths: `frontend/**`
- `pull_request` to `main`, `develop` — paths: `frontend/**`

### Steps
1. `actions/checkout@v4`
2. `actions/setup-node@v4` with Node 20, npm cache enabled
3. `npm ci` (working-directory: `frontend/`)
4. `npx ng lint` — ESLint 9 + @angular-eslint
5. `npx prettier --check "src/**/*.{ts,html,scss}"` — format check
6. `npx jest --coverage --ci` — Jest tests with 100% coverage gate
7. `npx ng build --configuration production` — production build validation

---

## Docker CI Pipeline (`docker-ci.yml`)

### Triggers
- `push` to `main`
- `pull_request` to `main`

### Steps
1. `actions/checkout@v4`
2. `docker compose build` — validate all images build cleanly

---

## Quality Gates

| Gate | Enforced By |
|---|---|
| 100% line + branch coverage (backend) | `--cov-fail-under=100 --cov-branch` in pyproject.toml addopts |
| 100% coverage (frontend) | Jest coverage thresholds in jest.config |
| Lint clean (backend) | `ruff check` non-zero exit on violation |
| Type-safe (backend) | `mypy --strict` non-zero exit on error |
| Lint clean (frontend) | `ng lint` non-zero exit on violation |
| Format consistent | `ruff format --check` / `prettier --check` |
| Production build | `ng build --configuration production` |

---

## Environment Variables

Backend CI injects:
- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/options_tracker_test`
- `SECRET_KEY=ci-secret` (placeholder for any app config)

---

## Decisions

- Use `snok/install-poetry@v1` for reliable Poetry setup on GitHub runners
- Pin action versions to `@v4` / `@v5` for stability
- PostgreSQL port mapped to `localhost:5432` via service container defaults
- Coverage artifact name: `backend-coverage-report` / `frontend-coverage-report`
- `docker-ci.yml` targets only `main` to avoid excessive image builds on feature branches
