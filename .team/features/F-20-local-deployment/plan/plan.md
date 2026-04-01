# F-20: Hybrid Local Deployment — Implementation Plan

**Status:** Implemented  
**Implemented by:** devops-qa-smoke-tester  
**Date:** 2026-04-01

---

## Files Created / Modified

| File | Action | Purpose |
|---|---|---|
| `docker-compose.dev.yml` | Created | DEV stack (ports 4200/8000/5432, hot-reload, bind mounts) |
| `docker-compose.qa.yml` | Created | QA stack (ports 4300/8100/5433, production build, nginx) |
| `docker-compose.prod.yml` | Created | PROD stack (ports 4400/8200/5434, production build, nginx) |
| `.env.dev.example` | Created | DEV env template (DEBUG logging, `options_tracker_dev` DB) |
| `.env.qa.example` | Created | QA env template (INFO logging, `options_tracker_qa` DB) |
| `.env.prod.example` | Created | PROD env template (WARNING logging, `options_tracker_prod` DB) |
| `backend/entrypoint.sh` | Created | Runs `alembic upgrade head` before uvicorn starts |
| `backend/Dockerfile` | Modified | Added `ENTRYPOINT ["/entrypoint.sh"]` above existing CMD |
| `frontend/Dockerfile` | Modified | Added `nginx` stage (builds prod bundle, serves via nginx) |
| `frontend/nginx.conf` | Created | nginx: serves static files + proxies `/api` → `http://backend:8000` |
| `Makefile` | Created | Full command set: setup, deploy-dev, promote-qa/prod, status, teardown, logs, smoke |
| `.gitignore` | Modified | Added `.env.dev`, `.env.qa`, `.env.prod`, `.version-*` entries |

---

## Architecture Decisions

### 1. Separate Compose Files (not profiles)
Each environment gets its own `docker-compose.{env}.yml`. No Docker profiles. This is intentional — explicit files make environment differences auditable and reduces accidental cross-environment operations.

### 2. Frontend Build Strategy per Environment

| Environment | Frontend Stage | API URL |
|---|---|---|
| DEV | `dev` (ng serve, bind mount) | `http://localhost:8000` (absolute, from `environment.ts`) |
| QA | `nginx` (production build + nginx) | `/api` (relative, from `environment.prod.ts`, proxied by nginx) |
| PROD | `nginx` (production build + nginx) | `/api` (relative, from `environment.prod.ts`, proxied by nginx) |

The `environment.prod.ts` uses a relative `/api` base URL. For QA/PROD, the nginx stage is used: nginx serves the production Angular bundle on port 80 and proxies `/api/*` to `http://backend:8000` (Docker-internal). The browser calls `http://localhost:4300/api/v1/...` → nginx forwards to the backend container.

DEV continues to use the `dev` stage (`ng serve`) which uses the absolute `http://localhost:8000` URL from `environment.ts` — no proxy needed.

### 3. Backend Entrypoint
`backend/entrypoint.sh` runs `alembic upgrade head` before starting uvicorn. This ensures migrations are always current on every deploy without any manual step. The entrypoint uses `exec "$@"` so the CMD (uvicorn) becomes PID 1, enabling clean signal handling.

### 4. QA/PROD Source via git worktree
`make promote-qa/prod` uses `git worktree add /tmp/options-tracker-{env} VERSION` to check out the tagged version without disturbing the working tree. The worktree is cleaned up after the build completes. The compose files in the worktree are used for building images; the `.env.{env}` files are read from the project root (not the worktree), keeping credentials out of git history.

### 5. Version Tracking
Each successful deploy writes a `.version-{env}` file (git tag or commit SHA). `make status` reads these files to display the current version per environment. These files are git-ignored.

### 6. Data Safety
`teardown-*` targets use `docker compose down` without `-v` — volumes are always preserved. No Makefile command deletes a volume. To wipe a database, the developer must explicitly run `docker volume rm options-tracker_postgres_data_{env}`.

---

## One-Time Developer Setup

```bash
# 1. Clone and set up env files
make setup

# 2. Edit credentials if needed (defaults work for local dev)
# nano .env.dev  (optional)

# 3. Deploy DEV
make deploy-dev
```

---

## Workflow: DEV → QA → PROD

```bash
# Work on main branch, all CI passes ...

# 1. Tag a release candidate
git tag v0.1-rc1

# 2. Promote to QA and smoke test
make promote-qa VERSION=v0.1-rc1
make smoke-qa

# 3. If smoke tests pass, tag stable and promote to PROD
git tag v0.1
make promote-prod VERSION=v0.1

# 4. Check status of all environments
make status
```

---

## Open Question Resolution (from requirements.md §10)

**Q1 — Angular API URL at build time:** Resolved. The existing `environment.prod.ts` uses `/api` (relative URL). For QA/PROD, nginx proxies `/api` → `http://backend:8000`. No Angular source changes needed.

**Q2 — Frontend proxy in DEV:** Resolved. In DEV, `ng serve` serves from `http://localhost:4200` and the frontend calls `http://localhost:8000` directly (absolute URL in `environment.ts`). No proxy config needed in DEV compose.

**Q3 — git worktrees:** Confirmed. `git worktree add` works with uncommitted changes on the current branch — the worktree checks out the specified tag independently. Works on Git 2.5+ (macOS ships Git 2.39+ via Xcode CLT).

---

## Acceptance Criteria Status

| # | Criterion | Status |
|---|---|---|
| AC-01 | `make setup` creates env files from examples | ✅ |
| AC-02 | `make deploy-dev` → localhost:4200 / localhost:8000 | ✅ |
| AC-03 | `make promote-qa VERSION=...` → localhost:4300 / localhost:8100 | ✅ |
| AC-04 | `make promote-prod VERSION=...` → localhost:4400 / localhost:8200 | ✅ |
| AC-05 | All three stacks run simultaneously, no port conflicts | ✅ (isolated ports + networks + volumes) |
| AC-06 | CSV upload to DEV does not affect QA/PROD | ✅ (separate DB containers + volumes) |
| AC-07 | `make status` shows versions and health | ✅ |
| AC-08 | `make teardown-qa` stops QA only | ✅ |
| AC-09 | Data volumes persist after teardown | ✅ (no `-v` in down command) |
| AC-10 | Alembic runs automatically on deploy | ✅ (entrypoint.sh) |
| AC-11 | `make promote-qa VERSION=nonexistent` fails clearly | ✅ |
| AC-12 | `make smoke-qa` targets localhost:8100 | ✅ |
| AC-13 | `make logs-dev` tails DEV logs | ✅ |
| AC-14 | Existing `docker compose up` unchanged | ✅ (docker-compose.yml not modified) |
| AC-15 | `.env.dev/.qa/.prod` not in git | ✅ (.gitignore updated) |
