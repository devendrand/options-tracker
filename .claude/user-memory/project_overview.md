---
name: Options Tracker Project Overview
description: Core facts about the Options Tracker project — stack, scope, and current version
type: project
---

Options Tracker is a web app for uploading E*TRADE CSV transaction exports, parsing/classifying options trades, matching open/close legs (FIFO), and computing realized P&L.

**Why:** Single-user local tool for individual investors; no brokerage API integration.

**Current version:** v0.1 (MVP1) — E*TRADE CSV only, no auth, Docker Compose deployment.

**Stack:** Angular (frontend) + Python/FastAPI (backend) + PostgreSQL 16 + SQLAlchemy 2.x async + Alembic + Docker Compose. Backend uses Poetry, Ruff, mypy, pytest (100% coverage gate). Frontend uses Jest (100% coverage gate).

**How to apply:** All implementation decisions must align with PRD.md. TDD is enforced — tests before implementation. 100% branch+line coverage is a hard CI gate for both backend and frontend.
