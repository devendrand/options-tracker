---
name: F-20 Deployment Infrastructure
description: Docker Compose multi-env setup (DEV/QA/PROD), Makefile commands, nginx proxy strategy, and entrypoint pattern for options-tracker
type: project
---

Three isolated local environments implemented in F-20:

| Env | Frontend | Backend | DB | Compose File | Source |
|---|---|---|---|---|---|
| DEV | 4200 | 8000 | 5432 | docker-compose.dev.yml | main HEAD + bind mount |
| QA | 4300 | 8100 | 5433 | docker-compose.qa.yml | git tag via worktree |
| PROD | 4400 | 8200 | 5434 | docker-compose.prod.yml | git tag via worktree |

**Frontend build strategy:**
- DEV: `target: dev` — ng serve with hot-reload; API calls to absolute `http://localhost:8000` (from environment.ts)
- QA/PROD: `target: nginx` — production build + nginx; API calls to `/api` (relative, from environment.prod.ts); nginx proxies `/api` → `http://backend:8000` (Docker-internal)

**Backend entrypoint:** `backend/entrypoint.sh` runs `alembic upgrade head` before uvicorn. Added as ENTRYPOINT in Dockerfile.

**Makefile commands:** `make setup`, `make deploy-dev`, `make promote-qa VERSION=x`, `make promote-prod VERSION=x`, `make status`, `make teardown-{dev,qa,prod}`, `make teardown-all`, `make logs-{dev,qa,prod}`, `make smoke-{dev,qa,prod}`

**Smoke tests:** `smoke-tests/run_smoke_tests.py` (standalone script, reads SMOKE_BASE_URL env var). Makefile `smoke-*` targets pass the correct base URL and DATABASE_URL per environment.

**Why:** Single developer on MacBook needs safe DEV → QA → PROD promotion workflow without disrupting running instances.

**How to apply:** When troubleshooting deployments, check `.version-{env}` files for current running version. Volumes are never auto-deleted — require explicit `docker volume rm options-tracker_postgres_data_{env}`.
