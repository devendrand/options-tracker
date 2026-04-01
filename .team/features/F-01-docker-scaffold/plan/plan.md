# F-01: Docker Compose + Environment Scaffold — Implementation Plan

**Owner:** devops-qa-smoke-tester  
**Status:** Approved  
**Date:** 2026-03-30  

---

## Objective

Create the Docker Compose scaffold that allows the full stack (PostgreSQL 16, FastAPI backend, Angular frontend) to start with `docker compose up --build` after a single `cp .env.example .env`.

---

## Files to Create

| File | Purpose |
|---|---|
| `.env.example` | Template for all required environment variables (committed) |
| `.gitignore` | Ensures `.env` (with real secrets) is never committed |
| `docker-compose.yml` | Orchestrates db, backend, frontend services with healthchecks |
| `backend/Dockerfile` | Multi-stage Python 3.12 + Poetry image; uvicorn entrypoint |
| `frontend/Dockerfile` | Multi-stage Node LTS image; ng serve (dev) / ng build (prod) |

---

## Design Decisions

### Environment Variables
- `.env.example` is committed and contains safe placeholder credentials for local dev.
- `.env` is gitignored and must be created by the developer before first run.
- All services consume `env_file: .env` so no secret is hardcoded in `docker-compose.yml`.

### Service Dependencies & Healthchecks
- **db**: PostgreSQL 16 healthcheck via `pg_isready -U ${POSTGRES_USER}`. No upstream dependency.
- **backend**: depends on `db` with condition `service_healthy`. Healthcheck hits `GET /docs` (FastAPI built-in) on port 8000.
- **frontend**: depends on `backend` with condition `service_healthy`. Healthcheck hits port 4200 via curl.

### Volume Strategy
- `db`: named volume `postgres_data` for persistence across `docker compose down` (without `-v`).
- `backend`: bind mount `./backend:/app` for hot-reload via uvicorn `--reload`.
- `frontend`: bind mount `./frontend:/app` + anonymous volume for `node_modules` to prevent host override.

### Backend Dockerfile (multi-stage)
- **Stage 1 (builder):** Install Poetry, export `requirements.txt`, install deps into `/install`.
- **Stage 2 (runtime):** Python 3.12-slim, copy installed deps, copy app code. Entrypoint: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
- `--reload` is acceptable for dev; production stage uses `ng build` / gunicorn (future).

### Frontend Dockerfile (multi-stage)
- **Stage 1 (dev):** Node LTS, `npm ci`, expose 4200, entrypoint `ng serve --host 0.0.0.0 --port 4200 --poll 500`.
- **Stage 2 (prod):** Separate target `ng build --configuration production`; output to `dist/`.
- Dev stage is the default target used by docker-compose.

---

## Acceptance Criteria

- [ ] `docker compose config` validates with no errors
- [ ] `.env.example` contains all 7 required variables
- [ ] `.env` is present in `.gitignore`
- [ ] All three services define a `healthcheck`
- [ ] `backend` depends on `db` (healthy); `frontend` depends on `backend` (healthy)
- [ ] No credentials in `docker-compose.yml` (all via env_file)
- [ ] `backend/Dockerfile` and `frontend/Dockerfile` both use multi-stage builds

---

## Risks

- **Frontend startup time:** `ng serve` can take 30–60 s to compile. The healthcheck `start_period` is set to 120 s to avoid false failures on first boot.
- **Backend scaffold not yet created:** `backend/` is currently empty. The Dockerfile uses a placeholder `app/main.py` check. The actual app is created in F-02. The container will fail to start until F-02 is complete — this is expected and acceptable at this scaffold stage.
