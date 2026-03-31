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

| ID | Feature | Priority | Status |
|---|---|---|---|
| F1 | Project Scaffolding (Docker, CI, DB) | P0 | pending |
| F2 | E*TRADE CSV Parser | P0 | pending |
| F3 | Transaction Upload API | P0 | pending |
| F4 | Upload Management API | P0 | pending |
| F5 | Transactions API | P1 | pending |
| F6 | Options Position Matching + P&L | P0 | pending |
| F7 | Positions API | P1 | pending |
| F8 | P&L Summary API | P1 | pending |
| F9 | Frontend Core Setup | P0 | pending |
| F10 | Frontend Dashboard | P1 | pending |
| F11 | Frontend Upload Page | P0 | pending |
| F12 | Frontend Transactions Page | P1 | pending |
| F13 | Frontend Positions Page | P1 | pending |
| F14 | Frontend Upload History Page | P1 | pending |

## Folder Structure

```
.team/
├── README.md               ← this file
├── features/
│   └── F{N}-{name}/
│       ├── plan/
│       │   └── plan.md     ← implementation plan (approved by tech-lead)
│       └── bugs/
│           └── BUG-*.md    ← bug fix addendums
├── decisions/              ← architectural decision records
├── open-questions/         ← BA-resolved open questions from PRD §11
└── smoke-tests/            ← devops smoke test results per feature
```

## Workflow

1. BA prioritizes features and resolves open questions
2. Relevant agent drafts implementation plan in `features/F{N}/plan/plan.md`
3. Tech Lead reviews and approves plan (or requests changes)
4. Agent implements using TDD
5. DevOps/QA runs smoke tests and validates feature
6. Tech Lead gives final go/no-go
