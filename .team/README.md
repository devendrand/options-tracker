# Options Tracker — Team Workspace

## Team Members

| Role | Responsibilities |
|---|---|
| **business-analyst** | Requirements prioritization, open question resolution, acceptance criteria |
| **backend-tdd-api-dev** | FastAPI endpoints, services (parser, classifier, deduplicator, matcher, pnl), TDD |
| **postgres-alembic-dev** | DB schema design, SQLAlchemy models, Alembic migrations, query optimization |
| **angular-tdd-frontend** | Angular components, services, routing, Jest tests |
| **tech-lead-architect** | Plan approval, architecture review, quality gates, go/no-go decisions |
| **devops-qa-smoke-tester** | CI/CD pipelines, Docker, smoke tests, environment validation |

## Feature Roadmap

| ID | Feature | Priority | Owner | Status |
|---|---|---|---|---|
| F-01 | Docker Compose + Environment Scaffold | Must Have | devops-qa-smoke-tester | pending |
| F-02 | Backend Project Scaffold (Poetry + FastAPI + Alembic) | Must Have | backend-tdd-api-dev | pending |
| F-03 | Frontend Project Scaffold (Angular + Jest + ESLint) | Must Have | angular-tdd-frontend | pending |
| F-04 | GitHub Actions CI Pipelines | Must Have | devops-qa-smoke-tester | pending |
| F-05 | Database Schema + Alembic Migrations | Must Have | postgres-alembic-dev | pending |
| F-06 | E*TRADE CSV Parser | Must Have | backend-tdd-api-dev | pending |
| F-07 | Transaction Classifier | Must Have | backend-tdd-api-dev | pending |
| F-08 | Deduplication Service | Must Have | backend-tdd-api-dev | pending |
| F-09 | Options Position Matcher (FIFO) | Must Have | backend-tdd-api-dev | pending |
| F-10 | P&L Calculation Service | Must Have | backend-tdd-api-dev | pending |
| F-11 | Covered Call Detection | Should Have | backend-tdd-api-dev | pending |
| F-12 | Upload API Endpoints | Must Have | backend-tdd-api-dev | pending |
| F-13 | Transactions + Positions + P&L API Endpoints | Must Have | backend-tdd-api-dev | in_progress |
| F-14 | Angular Core Services + HTTP Client Setup | Must Have | angular-tdd-frontend | approved (conditions) |
| F-15 | Upload Page | Must Have | angular-tdd-frontend | pending |
| F-16 | Transactions Page | Must Have | angular-tdd-frontend | pending |
| F-17 | Positions Page + Dashboard | Must Have | angular-tdd-frontend | pending |
| F-18 | Upload History + P&L Summary Pages | Should Have | angular-tdd-frontend | pending |
| F-19 | End-to-End Smoke Test Suite | Must Have | devops-qa-smoke-tester | pending |

## Dependency Tiers

```
Tier 0 — F-01, F-02, F-03, F-04 (Scaffold + CI — unblocks everything)
Tier 1 — F-05 (Database Schema — unblocks all backend services)
Tier 2 — F-06, F-07, F-08, F-09, F-10, F-11 (Backend Services — can parallelize)
Tier 3 — F-12, F-13 (API Endpoints — can parallelize)
Tier 4 — F-14, F-15, F-16, F-17, F-18 (Frontend UI — F-14 first, then F-15–F-18)
Tier 5 — F-19 (End-to-End Smoke Tests)
```

## Folder Structure

```
.team/
├── README.md               ← this file
├── features/
│   └── F-{NN}-{name}/
│       ├── plan/
│       │   └── plan.md     ← implementation plan (approved by tech-lead)
│       └── bugs/
│           └── BUG-*.md    ← bug fix addendums
├── decisions/              ← architectural decision records
├── open-questions/         ← BA-resolved open questions from PRD §11
└── smoke-tests/            ← devops smoke test results per feature
```

## Open Questions — All Resolved

| ID | Question | Resolution |
|---|---|---|
| OQ1 | Equity P&L in v0.1? | Include as Should Have — impacts F-10, F-12, F-13, F-17 |
| OQ2 | Partial close display? | One row + expandable drawer — impacts F-17 |
| OQ3 | P&L summary: month+year simultaneous? | One at a time with toggle — impacts F-13, F-18 |
| OQ4 | DRIP dividend handling? | No special handling — both rows as DIVIDEND — impacts F-06, F-07 |
| OQ5 | `Bought To Open`/`Sold To Close` support? | Confirmed required — impacts F-06, F-07 |

## Workflow

1. BA prioritizes features and resolves open questions
2. Relevant agent drafts implementation plan in `features/F-{NN}-{name}/plan/plan.md`
3. Tech Lead reviews and approves plan (or requests changes)
4. Agent implements using TDD
5. DevOps/QA runs smoke tests and validates feature
6. Tech Lead gives final go/no-go
