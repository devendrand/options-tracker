---
name: Project Context
description: Options Tracker PRD v0.4 (2026-03-30); feature numbering F-01 to F-20; all 5 OQs resolved; key decisions documented
type: project
---

Options Tracker v0.1 (MVP1) PRD is finalized as of 2026-03-30. Broker corrected to E*TRADE throughout.

Feature backlog uses F-01 through F-20 numbering (hyphenated, zero-padded). Old F1-F14 folder naming was retired 2026-03-30.

**Why:** Team workspace was restructured to align folder names with the authoritative backlog.md numbering.

**How to apply:** Always reference features as F-01 through F-19 in documentation and plans. Feature folders live at `.team/features/F-{NN}-{slug}/plan/plan.md`.

## All 5 Open Questions resolved (2026-03-30)

| OQ | Resolution Summary | Impacted Features |
|---|---|---|
| OQ1 Equity P&L | Include as Should Have in v0.1; equity close matching added to upload pipeline | F-10, F-12, F-13, F-17 |
| OQ2 Partial Close Display | One row per position + expandable drawer (lazy `GET /positions/{id}`) | F-17 |
| OQ3 P&L Summary Period | One period at a time (Month/Year toggle); default Year | F-13, F-18 |
| OQ4 DRIP Dividend | No special handling; both rows as DIVIDEND; no EquityPosition from DRIP in v0.1 | F-06, F-07 |
| OQ5 Bought To Open / Sold To Close | Both variants required; BTO/STC are unambiguous (no regex); SS/BTC require description regex | F-06, F-07 |

## F-20: Hybrid Local Deployment (added 2026-04-01)

F-20 requirements document created at `.team/features/F-20-local-deployment/plan/requirements.md`.

Key decisions captured in requirements:
- Three separate compose files: `docker-compose.dev.yml`, `docker-compose.qa.yml`, `docker-compose.prod.yml`
- Port matrix: DEV 4200/8000/5432 | QA 4300/8100/5433 | PROD 4400/8200/5434
- Per-environment DB names: `options_tracker_dev`, `options_tracker_qa`, `options_tracker_prod`
- QA and PROD deploy from git tags (not branch HEAD); DEV deploys `main` HEAD with hot-reload
- `git worktree` approach for tag-based builds (preserves working tree during promote)
- Alembic runs automatically in backend entrypoint before uvicorn starts
- 5 open questions logged: Angular API URL per env, frontend proxy, worktree compatibility, rollback strategy, DB port conflict on port 5432
- GitHub Actions CI is unchanged by F-20

## F-14 plan status
F-14 (Angular Core Services, formerly F9) has an approved-with-conditions plan. Conditions addressed: added /pnl-summary route stub, fixed RelativeDatePipe UTC timezone handling, added LoadingService concurrent-requests test. Plan migrated to F-14-angular-core-services/plan/plan.md on 2026-03-30.
