---
name: CI Pipeline Configuration
description: GitHub Actions CI workflow files, triggers, and quality gates for options-tracker
type: project
---

Three GitHub Actions workflows live in `.github/workflows/`:

- `backend-ci.yml` — triggers on push/PR to main+develop, paths `backend/**`. Steps: Python 3.12 + Poetry via `snok/install-poetry@v1`, ruff check, ruff format --check, mypy, pytest 100% coverage. PostgreSQL 16 service container on localhost:5432 (POSTGRES_USER/PASSWORD/DB env vars). Uploads coverage.xml artifact.
- `frontend-ci.yml` — triggers on push/PR to main+develop, paths `frontend/**`. Steps: Node 20 + npm ci, ng lint, prettier check, jest --coverage --ci, ng build --configuration production. Uploads coverage/ directory artifact.
- `docker-ci.yml` — triggers on push/PR to main only. Steps: checkout, docker/setup-buildx-action@v3, docker compose build.

**Why:** 100% coverage gate is CI-enforced per CLAUDE.md. PostgreSQL service container required because backend integration tests hit a real DB (no mocking).

**How to apply:** When diagnosing CI failures, check the relevant workflow file. DATABASE_URL env var is `postgresql+asyncpg://postgres:postgres@localhost:5432/options_tracker_test` in CI. Frontend coverage artifacts land in `frontend/coverage/`.
