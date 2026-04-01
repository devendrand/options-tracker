---
name: Deduplication Query Design for F-08
description: Recommended bulk LATERAL join pattern for F-08 deduplication, including NULL handling and index strategy
type: project
---

The F-08 deduplication service should use a single bulk query (temp table + LATERAL join) rather than per-row queries.

**Key decisions:**
- Use `IS NOT DISTINCT FROM` for nullable dedup fields (`settlement_date`, `price`) — plain `=` fails for NULLs.
- Use `LATERAL` subqueries with `LIMIT 1`: Tier 1 (exact 10-field match) checked first; Tier 2 (collision: trade_date + symbol + quantity + amount) only runs if Tier 1 found no match.
- Load incoming batch into a temp table or VALUES clause before running the dedup query.
- Use raw SQL / `text()` for the dedup query — SQLAlchemy ORM cannot express LATERAL or IS NOT DISTINCT FROM cleanly.
- No hash column in v0.1 — deferred due to single-user scale; revisit if dedup becomes a bottleneck.

**Required supporting index:**
`ix_transactions_dedup_collision` — partial composite index on `(trade_date, symbol, quantity, amount)` where `status != 'SOFT_DELETED'`. Must be created (via a new migration) before F-08 is implemented.

**Why:** Documented during DB dev review on 2026-03-31 as part of F-05 schema completeness review.

**How to apply:** When implementing F-08 deduplication service or the migration that adds the dedup index, follow this design. The full example query is in `.team/features/F-05-database-schema/plan/db-review.md`.
