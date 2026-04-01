## PLAN REVIEW: F-01 — Docker Compose + Environment Scaffold

**Reviewer:** tech-lead-architect  
**Date:** 2026-03-30  
**Plan file:** `.team/features/F-01-docker-scaffold/plan/plan.md`

---

### VERDICT: ⚠️ APPROVED WITH CONDITIONS

---

### Summary

The Docker Compose scaffold plan is well-structured: correct healthcheck chain, safe `.env` handling, multi-stage Dockerfiles, and appropriate bind-mount strategy for hot-reload development. Three minor gaps must be resolved before the implementation is considered complete.

---

### Strengths

- Correct dependency ordering: `db` → `backend` (service_healthy) → `frontend` (service_healthy). No service starts before its dependency is ready.
- Named volume `postgres_data` correctly persists data across `docker compose down` without `-v`.
- `.env.example` committed, `.env` gitignored — no credentials in version control.
- `node_modules` anonymous volume prevents the host bind mount from shadowing the container's installed packages (common Docker/Node pitfall, correctly handled).
- Honest risk assessment: explicitly flags that the backend container will fail to start until F-02 is complete.
- `start_period: 120s` on the frontend healthcheck correctly accommodates `ng serve` compile time.

---

### Issues Found

- **[MAJOR] `.env.example` variable list not enumerated in the plan**  
  The acceptance criterion states "`.env.example` contains all 7 required variables" but the plan never lists what those 7 variables are. Based on CLAUDE.md and the PRD, the required variables are at minimum:
  ```
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/options_tracker
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=postgres
  POSTGRES_DB=options_tracker
  POSTGRES_PORT=5432
  LOG_LEVEL=INFO
  ```
  That is 6 variables. If the 7th is `BACKEND_PORT` or `FRONTEND_PORT`, it must be specified. The implementation must define and document all variables before this feature is marked complete.

- **[MINOR] `uvicorn --reload` hardcoded in Dockerfile `CMD`**  
  The backend Dockerfile entrypoint uses `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`. The `--reload` flag is a dev-only flag (watches filesystem for changes; incompatible with production). If CI runs `docker compose build` and then executes the container to run integration tests, it will inadvertently run with `--reload`. Recommendation: pass `--reload` via the `command:` override in `docker-compose.yml` rather than baking it into the Dockerfile `CMD`. The Dockerfile `CMD` should be the production-safe baseline.

- **[MINOR] Backend healthcheck endpoint**  
  Using `GET /docs` (Swagger UI) as the backend healthcheck target works, but Swagger UI is a heavier endpoint (renders HTML, loads JS). A dedicated `GET /health` endpoint returning `{"status": "ok"}` is the conventional approach and is faster. Not a blocker for MVP1, but should be added in F-02 alongside the FastAPI scaffold.

---

### Required Changes Before Proceeding

1. **List all `.env.example` variables explicitly** — both in the plan and in the actual file. The implementation must not be declared complete until all required env vars are enumerated and validated against service startup.

2. **Move `--reload` out of the Dockerfile `CMD`** — the Dockerfile `CMD` should run uvicorn without `--reload`; the `docker-compose.yml` dev service should use a `command:` override to add `--reload` for local development. This keeps the image production-safe.

---

### Recommendations

- Add `HEALTHCHECK` instruction directly in the backend `Dockerfile` (in addition to the Compose healthcheck) so the image health is reportable even outside Compose.
- Consider adding a `docker-compose.override.yml` pattern for local dev overrides (bind mounts, `--reload`, debug ports) so the base `docker-compose.yml` is closer to production parity. Not required for MVP1.
