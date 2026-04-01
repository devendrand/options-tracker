# F-20: Hybrid Local Deployment (DEV / QA / PROD) — Requirements

**Feature ID:** F-20  
**Owner:** devops-qa-smoke-tester  
**BA:** business-analyst  
**Status:** Draft — Pending Implementation Plan  
**Depends on:** F-01, F-04, F-19  
**Priority:** Should Have  

---

## 1. Overview

### Business Context

Options Tracker is deployed on a single developer's MacBook via Docker Compose. Today there is one environment (the default `docker compose up`). The developer needs three isolated local environments to safely move code from active development through smoke-tested release candidate to a stable daily-use version — without disrupting a running instance during development.

### Primary Stakeholder

Single developer (owner/operator) managing their own trade data on a MacBook.

### Business Objective

Enable safe, reproducible local promotion of releases through DEV → QA → PROD using simple `make` commands, with each environment completely isolated (separate ports, separate databases, separate volumes).

### Scope

**In scope:**
- Three local Docker Compose environments (DEV, QA, PROD) on a single MacBook
- Makefile lifecycle commands (deploy, promote, status, teardown, logs)
- Per-environment config files (`.env.dev`, `.env.qa`, `.env.prod`)
- Separate Docker Compose files per environment
- Git tagging workflow for versioned promotions
- Automatic Alembic migration execution on deploy
- Smoke test targeting via environment-specific base URLs
- GitHub Actions CI unchanged (CI validates code quality only; does not deploy locally)

**Out of scope:**
- Remote deployments (no cloud, no VPS, no Kubernetes)
- Docker image registry push/pull (images built locally only in v0.1)
- Automated promotion pipelines (all promotions are manual `make` commands)
- Rollback automation (teardown + re-deploy at previous tag is the rollback procedure)
- Parallel database migration with zero downtime
- Multi-user or shared environments
- Hot-reload (`--reload`) in QA or PROD environments

---

## 2. Environment Matrix

| Attribute | DEV | QA | PROD |
|---|---|---|---|
| **Purpose** | Latest `main`, hot-reload dev work | Smoke-tested release candidate | Stable daily-use version |
| **Frontend Port** | 4200 | 4300 | 4400 |
| **Backend Port** | 8000 | 8100 | 8200 |
| **Database Port** | 5432 | 5433 | 5434 |
| **Database Name** | `options_tracker_dev` | `options_tracker_qa` | `options_tracker_prod` |
| **Docker Volume** | `postgres_data_dev` | `postgres_data_qa` | `postgres_data_prod` |
| **Log Level** | `DEBUG` | `INFO` | `WARNING` |
| **Backend Hot-Reload** | Yes (`--reload`) | No | No |
| **Source** | `main` branch HEAD | Git tag (e.g. `v0.1-rc1`) | Git tag (e.g. `v0.1`) |
| **Trigger** | `make deploy-dev` | `make promote-qa VERSION=x` | `make promote-prod VERSION=x` |
| **Compose file** | `docker-compose.dev.yml` | `docker-compose.qa.yml` | `docker-compose.prod.yml` |
| **Env file** | `.env.dev` | `.env.qa` | `.env.prod` |

---

## 3. User Stories

### US-01: Run latest development build
**As a** developer  
**I want to** deploy the latest `main` branch to a local DEV environment with a single command  
**So that** I can immediately test my work-in-progress without manual Docker steps.

**Acceptance Criteria:**
- `make deploy-dev` checks out `main`, builds images, starts all three containers (db, backend, frontend)
- Frontend available at `localhost:4200`, backend at `localhost:8000`, DB at `localhost:5432`
- Backend runs with `--reload` and code bind-mounted; file changes in `./backend` are reflected without restart
- Alembic migrations run automatically before the backend starts accepting requests
- Previously running DEV stack (if any) is replaced without manual teardown

---

### US-02: Promote a release candidate to QA
**As a** developer  
**I want to** deploy a specific git tag to a QA environment  
**So that** I can run smoke tests against a clean, tagged build before calling it production-ready.

**Acceptance Criteria:**
- `make promote-qa VERSION=v0.1-rc1` checks out the git tag `v0.1-rc1`, builds images from that tag's source, and starts the QA stack
- QA stack is completely independent of DEV: different ports, different database, no shared volumes
- Backend does NOT run with `--reload`; source is not bind-mounted — the image contains the built code
- Alembic migrations run automatically against the QA database before the backend starts
- `make promote-qa` fails fast with a clear error if the git tag does not exist locally

---

### US-03: Promote a stable release to PROD
**As a** developer  
**I want to** deploy a verified git tag to a PROD environment  
**So that** I have a stable, isolated instance for my daily options tracking.

**Acceptance Criteria:**
- `make promote-prod VERSION=v0.1` checks out the git tag `v0.1`, builds images from that tag's source, and starts the PROD stack
- PROD stack is completely independent of DEV and QA
- The same VERSION that passed smoke tests on QA must be deployable to PROD unchanged
- Alembic migrations run automatically against the PROD database

---

### US-04: See which version each environment is running
**As a** developer  
**I want to** run a single command to see the status of all three environments  
**So that** I always know what version is live in each environment without inspecting Docker manually.

**Acceptance Criteria:**
- `make status` prints a table showing: environment name, current git tag or branch, container health (up/down/unhealthy), frontend URL, backend URL
- Output is human-readable, not raw JSON
- Environments that are not running show `STOPPED` — not an error

---

### US-05: Stop an environment
**As a** developer  
**I want to** stop a specific environment without affecting the others  
**So that** I can free up resources when not using a particular environment.

**Acceptance Criteria:**
- `make teardown-dev`, `make teardown-qa`, `make teardown-prod` each stop only their target stack
- Stopping DEV does not affect QA or PROD containers
- Data volumes are preserved on teardown (not `down -v`); data is only deleted if the developer explicitly intends to wipe the database
- Running `teardown` on a stopped environment is a no-op (no error)

---

### US-06: Tail logs for an environment
**As a** developer  
**I want to** follow logs for any running environment  
**So that** I can debug issues during or after a deployment.

**Acceptance Criteria:**
- `make logs-dev`, `make logs-qa`, `make logs-prod` tail all container logs for that environment
- Output follows (i.e. `docker compose logs -f`) until interrupted with Ctrl+C
- Running logs on a stopped environment prints a clear message and exits cleanly

---

### US-07: Run smoke tests against any environment
**As a** developer  
**I want to** target the F-19 smoke test suite at a specific environment  
**So that** I can validate QA before promoting to PROD.

**Acceptance Criteria:**
- `make smoke-dev`, `make smoke-qa`, `make smoke-prod` run the existing F-19 smoke suite against the correct backend URL for that environment
- Smoke test commands pass `SMOKE_BASE_URL` and `DATABASE_URL` matching the target environment to `pytest`
- A failed smoke test exits non-zero so the developer gets a clear go/no-go signal
- Smoke tests do not require any code changes — they read the environment from env vars (F-19 compliance)

---

## 4. Functional Requirements

### FR-01: Separate Docker Compose Files per Environment

**Description:** Three Docker Compose files (`docker-compose.dev.yml`, `docker-compose.qa.yml`, `docker-compose.prod.yml`) define the stack for each environment with isolated port mappings and named volumes.

**Actor(s):** Makefile (invokes `docker compose -f ... --env-file ... up -d`)

**Preconditions:** The corresponding `.env.{env}` file exists with all required variables.

**Main Flow:**
1. Makefile invokes `docker compose -f docker-compose.{env}.yml --env-file .env.{env} up -d --build`
2. Compose reads port bindings, volume names, and env vars from the env-specific file
3. Three services start: db, backend, frontend (with healthchecks)
4. Backend waits for db healthy; frontend waits for backend healthy

**Alternate Flows:**
- If the env file is missing, `docker compose` exits with error; Makefile prints a clear message: "Run `cp .env.{env}.example .env.{env}` first"

**Acceptance Criteria:**
- Given the QA compose file is started, When the frontend loads at `localhost:4300`, Then requests proxy to backend at `localhost:8100` (not 8000)
- Given DEV and QA are both running, When I query `docker ps`, Then I see 6 containers (3 per env) with no port conflicts
- Given a PROD stack is running, When I stop it, Then DEV and QA containers are unaffected

**Priority:** Must Have  
**Dependencies:** FR-02, FR-03

---

### FR-02: Per-Environment Config Files

**Description:** Three example env files (`.env.dev.example`, `.env.qa.example`, `.env.prod.example`) are committed to source control. Developers copy them to the untracked `.env.dev`, `.env.qa`, `.env.prod`.

**Actor(s):** Developer (one-time setup)

**Main Flow:**
1. Developer runs `make setup` (or manually copies) to create the three env files
2. Each file contains port variables, DB credentials, DB name, DATABASE_URL, LOG_LEVEL
3. `DATABASE_URL` for QA and PROD uses the container service name `db` as hostname (internal Docker network); external port differs per env

**Acceptance Criteria:**
- Given `.env.qa.example` is copied to `.env.qa`, When `make promote-qa VERSION=v0.1-rc1` runs, Then containers start on QA ports without editing any file
- Given `.env.dev`, `.env.qa`, `.env.prod` all exist, Then no two DATABASE_URL values share the same DB name
- `.env.dev`, `.env.qa`, `.env.prod` are listed in `.gitignore`

**Priority:** Must Have  
**Dependencies:** None

---

### FR-03: Makefile Command Set

**Description:** A root-level `Makefile` provides all lifecycle commands. Commands are environment-aware and delegate to the correct compose file and env file.

**Actor(s):** Developer

**Commands and Acceptance Criteria:**

#### `make deploy-dev`
- Runs from `main` branch HEAD (does not require uncommitted changes to be stashed, but warns if working tree is dirty)
- Executes: `docker compose -f docker-compose.dev.yml --env-file .env.dev up -d --build`
- Previously running DEV containers are replaced (compose handles this natively)
- Backend container entrypoint runs `alembic upgrade head` before starting uvicorn

#### `make promote-qa VERSION=v0.1-rc1`
- Fails with usage error if `VERSION` is not provided
- Fails with clear error if `git tag -l v0.1-rc1` returns empty (tag does not exist)
- Checks out the tag in a temporary git worktree (does not discard current working directory changes)
- Builds images from the worktree source
- Starts QA stack from that tag's images
- Cleans up the temporary worktree on completion

#### `make promote-prod VERSION=v0.1`
- Same mechanics as `promote-qa` but targets PROD ports/volumes
- Does not require QA smoke tests to have passed (that is the developer's responsibility)

#### `make status`
- Outputs a formatted table: environment, version (git tag or branch name), frontend URL, backend URL, container status
- Reads version from a `.version` label file written to the compose project directory at deploy time, or falls back to `docker inspect` labels
- Works even when some environments are stopped

#### `make teardown-dev` / `make teardown-qa` / `make teardown-prod`
- Runs `docker compose -f docker-compose.{env}.yml --env-file .env.{env} down` (no `-v`; volumes preserved)
- Prints: "DEV environment stopped. Data volume postgres_data_dev preserved."

#### `make logs-dev` / `make logs-qa` / `make logs-prod`
- Runs `docker compose -f docker-compose.{env}.yml --env-file .env.{env} logs -f`

#### `make smoke-dev` / `make smoke-qa` / `make smoke-prod`
- Reads the correct `SMOKE_BASE_URL` and `DATABASE_URL` for the target environment
- Runs `cd backend && poetry run pytest tests/smoke/ -v --no-cov`

**Priority:** Must Have  
**Dependencies:** FR-01, FR-02

---

### FR-04: Automatic Alembic Migration on Deploy

**Description:** When a backend container starts, it runs `alembic upgrade head` against its environment's database before uvicorn begins accepting connections.

**Actor(s):** Backend Docker entrypoint

**Main Flow:**
1. Backend container starts
2. Entrypoint script runs `alembic upgrade head`
3. If migration succeeds, uvicorn starts
4. If migration fails (e.g. DB not ready, schema conflict), container exits with error code — Docker Compose healthcheck reports unhealthy

**Acceptance Criteria:**
- Given a fresh QA database (first deploy), When `make promote-qa` runs, Then all Alembic migrations apply and the backend starts without manual steps
- Given QA already has migrations at revision N, When a new version with revision N+1 is promoted, Then only the new migration runs on startup
- Given a migration fails, Then the backend container exits non-zero and `make promote-qa` reports an error

**Priority:** Must Have  
**Dependencies:** FR-01

---

### FR-05: Git Tagging Workflow

**Description:** Versions are identified by git tags. Promotions to QA and PROD always use a tag — never a branch name or `HEAD`.

**Actor(s):** Developer

**Tagging Convention:**
- Release candidates: `v{major}.{minor}-rc{n}` (e.g. `v0.1-rc1`, `v0.1-rc2`)
- Stable releases: `v{major}.{minor}` (e.g. `v0.1`)
- Tags are created manually by the developer: `git tag v0.1-rc1 && git push origin v0.1-rc1`

**Main Flow:**
1. Developer finishes a feature on `main`, all CI passes
2. Developer creates a tag: `git tag v0.1-rc1`
3. Developer runs `make promote-qa VERSION=v0.1-rc1`
4. Smoke tests pass
5. Developer creates a stable tag: `git tag v0.1`
6. Developer runs `make promote-prod VERSION=v0.1`

**Acceptance Criteria:**
- `make promote-qa VERSION=v0.1-rc1` only succeeds if `v0.1-rc1` is a valid local git tag
- If the developer passes a branch name (e.g. `VERSION=main`) instead of a tag, the Makefile warns: "VERSION should be a git tag, not a branch name" and prompts for confirmation before proceeding
- Tags are not auto-created by Makefile commands

**Priority:** Should Have  
**Dependencies:** FR-03

---

### FR-06: Database Isolation

**Description:** Each environment uses a completely independent PostgreSQL container with its own named Docker volume. Cross-contamination between environments is architecturally impossible.

**Actor(s):** Docker Compose (infrastructure)

**Acceptance Criteria:**
- Given DEV, QA, and PROD are all running, Then `docker volume ls` shows three distinct volumes: `postgres_data_dev`, `postgres_data_qa`, `postgres_data_prod`
- Given I upload a CSV to DEV, Then `GET /api/v1/transactions` on QA (port 8100) returns an empty list
- Given QA data volume exists, When `make teardown-qa` runs, Then the volume persists and data survives the teardown
- Given I need to wipe a database, Then the developer must explicitly run `docker volume rm options-tracker_postgres_data_qa` — no Makefile command does this automatically

**Priority:** Must Have  
**Dependencies:** FR-01, FR-02

---

### FR-07: One-Time Setup Command

**Description:** `make setup` creates all three env files from their examples if they do not already exist. This is the only command a developer needs to run on a fresh clone before using the system.

**Actor(s):** Developer

**Acceptance Criteria:**
- Given a fresh clone with no env files, When `make setup` runs, Then `.env.dev`, `.env.qa`, `.env.prod` are created from their respective `.example` files
- If an env file already exists, `make setup` does not overwrite it (idempotent)
- `make setup` prints: "Created .env.dev, .env.qa, .env.prod — edit credentials if needed before deploying"

**Priority:** Should Have  
**Dependencies:** FR-02

---

## 5. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Isolation | No port conflicts between any two environments. Port ranges: DEV 4200/8000/5432, QA 4300/8100/5433, PROD 4400/8200/5434. |
| NFR-02 | Performance | `make deploy-dev` completes in under 3 minutes on a cold build (all layers cached: under 60 seconds). |
| NFR-03 | Reliability | Stopping one environment must have zero effect on the other two. |
| NFR-04 | Simplicity | No new tooling beyond `make`, `docker compose`, `git`, and existing `poetry`. Developer does not need to learn any new CLI tools. |
| NFR-05 | Gitignore | `.env.dev`, `.env.qa`, `.env.prod` are never committed to source control. Only `.example` variants are committed. |
| NFR-06 | CI Independence | GitHub Actions CI pipelines (backend-ci.yml, frontend-ci.yml, docker-ci.yml) are unchanged by F-20. CI does not deploy to local environments. |
| NFR-07 | Data Safety | No Makefile command wipes a database volume automatically. Volume destruction requires an explicit `docker volume rm` command. |
| NFR-08 | Portability | Makefile commands work on macOS (zsh/bash). GNU Make 3.81+ (shipped with macOS via Xcode CLT). No GNU-specific Makefile extensions that break BSD make. |

---

## 6. Deployment Flow Diagrams

### DEV Deploy Flow (`make deploy-dev`)

```
Developer runs: make deploy-dev
        │
        ▼
Assert .env.dev exists (fail fast if missing)
        │
        ▼
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d --build
        │
        ├─► Build backend image (from ./backend, current working tree)
        ├─► Build frontend image (target: dev)
        ▼
db container starts
  └─► healthcheck passes (pg_isready)
        │
        ▼
backend container starts
  └─► entrypoint: alembic upgrade head
  └─► uvicorn --reload --host 0.0.0.0 --port 8000
  └─► healthcheck passes (curl /health)
        │
        ▼
frontend container starts
  └─► ng serve --host 0.0.0.0 --port 4200
  └─► healthcheck passes (curl localhost:4200)
        │
        ▼
Write .version-dev = "main@{commit_sha}"
        │
        ▼
Print: "DEV deployed → http://localhost:4200"
```

---

### QA Promote Flow (`make promote-qa VERSION=v0.1-rc1`)

```
Developer runs: make promote-qa VERSION=v0.1-rc1
        │
        ▼
Assert VERSION is set (fail: "Usage: make promote-qa VERSION=vX.Y-rcN")
        │
        ▼
Assert git tag v0.1-rc1 exists (fail: "Tag v0.1-rc1 not found. Run: git tag v0.1-rc1")
        │
        ▼
Assert .env.qa exists (fail: "Run: cp .env.qa.example .env.qa")
        │
        ▼
git worktree add /tmp/options-tracker-qa v0.1-rc1
        │
        ▼
docker compose -f /tmp/options-tracker-qa/docker-compose.qa.yml
               --env-file .env.qa
               --project-directory .
               up -d --build
        │
        ├─► Build backend image (from worktree source at v0.1-rc1, NO --reload)
        ├─► Build frontend image (target: prod, ng build --configuration production)
        ▼
db-qa container starts (port 5433, volume postgres_data_qa)
  └─► healthcheck passes
        │
        ▼
backend-qa container starts
  └─► entrypoint: alembic upgrade head (against options_tracker_qa DB)
  └─► uvicorn --host 0.0.0.0 --port 8100 (no --reload)
  └─► healthcheck passes
        │
        ▼
frontend-qa container starts (port 4300, proxies to backend:8100)
  └─► healthcheck passes
        │
        ▼
git worktree remove /tmp/options-tracker-qa
        │
        ▼
Write .version-qa = "v0.1-rc1"
        │
        ▼
Print: "QA deployed → http://localhost:4300 (v0.1-rc1)"
Print: "Run smoke tests: make smoke-qa"
```

---

### Status Output (`make status`)

```
$ make status

Environment  Version        Frontend              Backend               DB              Status
───────────  ─────────────  ──────────────────    ──────────────────    ────────────    ──────
DEV          main@a1b2c3d   http://localhost:4200  http://localhost:8000  localhost:5432  HEALTHY
QA           v0.1-rc1       http://localhost:4300  http://localhost:8100  localhost:5433  HEALTHY
PROD         (not running)  http://localhost:4400  http://localhost:8200  localhost:5434  STOPPED
```

---

## 7. Environment Configuration Matrix

### `.env.dev.example`

```dotenv
# DEV environment — copy to .env.dev, do not commit .env.dev
POSTGRES_USER=options_tracker
POSTGRES_PASSWORD=options_tracker_dev
POSTGRES_DB=options_tracker_dev

DATABASE_URL=postgresql+asyncpg://options_tracker:options_tracker_dev@db:5432/options_tracker_dev

LOG_LEVEL=DEBUG
BACKEND_PORT=8000
FRONTEND_PORT=4200
DB_PORT=5432
```

### `.env.qa.example`

```dotenv
# QA environment — copy to .env.qa, do not commit .env.qa
POSTGRES_USER=options_tracker
POSTGRES_PASSWORD=options_tracker_qa
POSTGRES_DB=options_tracker_qa

DATABASE_URL=postgresql+asyncpg://options_tracker:options_tracker_qa@db:5432/options_tracker_qa

LOG_LEVEL=INFO
BACKEND_PORT=8100
FRONTEND_PORT=4300
DB_PORT=5433
```

### `.env.prod.example`

```dotenv
# PROD environment — copy to .env.prod, do not commit .env.prod
POSTGRES_USER=options_tracker
POSTGRES_PASSWORD=options_tracker_prod
POSTGRES_DB=options_tracker_prod

DATABASE_URL=postgresql+asyncpg://options_tracker:options_tracker_prod@db:5432/options_tracker_prod

LOG_LEVEL=WARNING
BACKEND_PORT=8200
FRONTEND_PORT=4400
DB_PORT=5434
```

---

## 8. Makefile Command Reference

| Command | Arguments | Description |
|---|---|---|
| `make setup` | — | Create `.env.{dev,qa,prod}` from examples (idempotent) |
| `make deploy-dev` | — | Build and deploy `main` HEAD to DEV environment |
| `make promote-qa` | `VERSION=vX.Y-rcN` | Deploy a specific git tag to QA environment |
| `make promote-prod` | `VERSION=vX.Y` | Deploy a specific git tag to PROD environment |
| `make status` | — | Show version and health of all three environments |
| `make teardown-dev` | — | Stop DEV containers (preserve data volume) |
| `make teardown-qa` | — | Stop QA containers (preserve data volume) |
| `make teardown-prod` | — | Stop PROD containers (preserve data volume) |
| `make logs-dev` | — | Tail all DEV container logs (Ctrl+C to exit) |
| `make logs-qa` | — | Tail all QA container logs |
| `make logs-prod` | — | Tail all PROD container logs |
| `make smoke-dev` | — | Run F-19 smoke suite against DEV (port 8000) |
| `make smoke-qa` | — | Run F-19 smoke suite against QA (port 8100) |
| `make smoke-prod` | — | Run F-19 smoke suite against PROD (port 8200) |

---

## 9. Constraints and Assumptions

### Constraints

1. **MacBook only.** This deployment topology runs exclusively on the developer's local machine. Remote access, ingress, and TLS are out of scope.

2. **No image registry.** Images are always built locally from source. There is no `docker push` or `docker pull` step. A future F-21 could add registry support for sharing builds across machines.

3. **Single Makefile, root level.** All commands live in the root `Makefile`. The existing `docker-compose.yml` (used by CI) is not modified or deleted; the three new compose files are additive.

4. **Existing CI untouched.** `backend-ci.yml`, `frontend-ci.yml`, and `docker-ci.yml` continue to use the existing `docker-compose.yml` and `.env.example`. No CI changes in F-20.

5. **GNU Make 3.81+.** macOS ships Make 3.81 via Xcode Command Line Tools. The Makefile must be compatible with this version (no `$(shell …)` in prerequisites, no `::` rules, no `$(eval …)` inside recipes unless using `.ONESHELL`).

6. **Docker Desktop required.** Developer must have Docker Desktop for Mac installed. No Colima or Rancher Desktop variants are explicitly supported (though they should work with standard Docker CLI).

### Assumptions

1. The developer has the git tag checked out or fetched locally before running `make promote-qa/prod`. The Makefile does not perform `git fetch` automatically (avoids unintended network side effects).

2. The existing `docker-compose.yml` (root) continues to work for CI (`docker compose build` in `docker-ci.yml`). The new per-environment files co-exist alongside it.

3. Smoke tests (F-19) are implemented and working before F-20 is considered complete. `make smoke-*` commands depend on `backend/tests/smoke/` existing.

4. The backend already has an entrypoint script or Dockerfile `CMD` that can be modified to run Alembic before uvicorn. If not, a lightweight `entrypoint.sh` wrapper is added to `backend/`.

5. The Angular frontend uses `environment.ts` / `environment.prod.ts` for the API base URL. In the QA and PROD Dockerfiles (built with `ng build --configuration production`), the API URL is baked in at build time pointing to the correct backend port via environment substitution or Angular environments config. This is a build-time concern, not runtime.

6. The developer creates git tags manually. No CI/CD automation creates tags.

---

## 10. Open Questions

1. **Angular API base URL at build time:** QA frontend (built as `production`) must point to `http://localhost:8100`, not `http://localhost:8000`. Does the existing `environment.prod.ts` support an injectable API URL at build time (via `--build-arg` or Angular file replacement)? Or does Angular need a third environment config (e.g. `environment.qa.ts`) with a separate build configuration? — **Requires input from angular-tdd-frontend.**

2. **Frontend proxy in DEV:** The current `docker-compose.yml` does not define a proxy configuration for the Angular dev server. If the frontend container proxies `/api/v1/` to the backend, does the proxy target need to change per environment? Or does the frontend always call the backend directly by URL? — **Clarify before implementing FR-01.**

3. **`make promote-*` and git worktrees:** Using `git worktree add` requires the repo to support worktrees (standard in Git 2.5+). Confirm this approach works when the developer has uncommitted changes on `main` (worktree uses the tag checkout, not the working tree). Alternative: stash + checkout + build + checkout back. Prefer worktree for cleanliness. — **Implementer to confirm.**

4. **Rollback procedure:** When PROD is running `v0.1` and a bad upload corrupts data, is the expectation to: (a) teardown PROD and re-deploy `v0.1` from scratch (empty DB), or (b) restore from a volume backup? Volume backup strategy is not defined. — **Defer to v1.0 unless user requests it.**

5. **Port conflicts on MacBook:** Ports 5432, 5433, 5434 for PostgreSQL assume nothing else is using those ports. If the developer has a local Postgres installation on 5432, DEV's DB port will conflict. Should the DB external ports be configurable per env (via `.env.dev`)? — **Yes, `DB_PORT` is already in the env file matrix. Confirm the compose file uses `${DB_PORT}:5432` for host-side binding.**

---

## 11. Out of Scope

| Item | Reason |
|---|---|
| Remote/cloud deployment | Single developer, local only in v0.1 |
| Docker image registry | No sharing across machines needed in v0.1 |
| Automated promotion triggers (CI/CD) | All promotions are manual; keep it simple |
| Rollback automation | Manual `teardown + promote` is sufficient for one developer |
| Data migration between environments (DEV→PROD) | Environments have isolated databases; no data sync in v0.1 |
| Health alerting or monitoring | No always-on monitoring; developer checks manually |
| TLS / HTTPS | Local development only; HTTP acceptable |
| Automated git tagging | Developer creates tags manually |
| Wipe-database Makefile command | Intentionally absent — data safety requires explicit `docker volume rm` |
| Multi-developer shared local environments | Single developer only in v0.1 |

---

## 12. Acceptance Criteria Summary (Go / No-Go)

All of the following must pass before F-20 is marked DONE:

| # | Criterion |
|---|---|
| AC-01 | `make setup` creates all three env files from examples without error on a fresh clone |
| AC-02 | `make deploy-dev` starts DEV stack; frontend responds at `localhost:4200`, backend at `localhost:8000` |
| AC-03 | `make promote-qa VERSION=v0.1-rc1` starts QA stack; frontend responds at `localhost:4300`, backend at `localhost:8100` |
| AC-04 | `make promote-prod VERSION=v0.1` starts PROD stack; frontend responds at `localhost:4400`, backend at `localhost:8200` |
| AC-05 | All three stacks run simultaneously with no port conflicts |
| AC-06 | Uploading a CSV to DEV does not affect QA or PROD databases |
| AC-07 | `make status` correctly shows versions and health for all three environments |
| AC-08 | `make teardown-qa` stops QA containers; DEV and PROD remain running and unaffected |
| AC-09 | Data volumes persist after teardown; re-deploying same version shows previous data |
| AC-10 | Alembic migrations run automatically on fresh deploy (no manual `alembic upgrade head` needed) |
| AC-11 | `make promote-qa VERSION=nonexistent` fails with a clear error message, no containers started |
| AC-12 | `make smoke-qa` runs F-19 smoke suite against `localhost:8100` and reports pass/fail |
| AC-13 | `make logs-dev` tails DEV logs; Ctrl+C exits cleanly |
| AC-14 | Existing `docker compose up` (using root `docker-compose.yml` + `.env`) continues to work unchanged |
| AC-15 | `.env.dev`, `.env.qa`, `.env.prod` are not committed to git (`.gitignore` enforced) |
