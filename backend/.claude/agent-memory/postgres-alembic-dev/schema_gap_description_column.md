---
name: Schema Gap — Missing description column on transactions
description: transactions.description is missing but is required for the 10-field F-08 dedup composite key and classifier disambiguation
type: project
---

The `transactions` table is missing a `description` column. CLAUDE.md specifies a 10-field dedup composite key that includes `description` (the raw CSV description/activity text). Without it:

1. Tier 1 exact-match deduplication (F-08) cannot be implemented as specified.
2. The classifier must reach back to `raw_transactions.raw_data` JSONB to disambiguate `Sold Short` / `Bought To Cover`.

**Why:** The field was simply omitted from the initial F-05 schema. Discovered during DB dev review on 2026-03-31.

**How to apply:** A new migration adding `description TEXT NULLABLE` to `transactions` must be written and merged before F-08 work starts. The column should be nullable to avoid locking issues on existing rows. Document the migration as an F-08 prerequisite.
