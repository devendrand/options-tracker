---
name: Docker Compose Scaffold
description: Key details about the Docker Compose setup for local dev — service names, ports, healthcheck patterns, volume strategy
type: project
---

F-01 Docker Compose scaffold is complete. Key facts:

- Services: `db` (postgres:16-alpine), `backend` (FastAPI/uvicorn), `frontend` (Angular/ng serve)
- Ports: db=5432, backend=8000, frontend=4200
- backend depends on db (service_healthy); frontend depends on backend (service_healthy)
- Healthchecks: db uses `pg_isready`, backend hits `/docs`, frontend hits port 4200 via curl
- Volumes: `postgres_data` named volume for db; bind mounts for backend and frontend hot-reload; anonymous `/app/node_modules` volume on frontend to prevent host override
- All env vars via `env_file: .env`; `.env.example` is committed, `.env` is gitignored
- Backend Dockerfile: multi-stage, Python 3.12-slim, Poetry export → requirements.txt, uvicorn --reload entrypoint
- Frontend Dockerfile: multi-stage, Node LTS alpine; dev stage = ng serve --poll 500; prod stage = ng build + serve

**Why:** Backend and frontend containers are empty shells until F-02 and F-03 scaffold the actual apps — expected to fail startup until then.

**How to apply:** When writing CI jobs or smoke tests, reference these service names and ports. Startup times: db ~10s, backend ~30s, frontend ~120s (ng compile on first boot).
