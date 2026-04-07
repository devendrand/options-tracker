---
name: Backend API contracts and schema conventions
description: Established patterns for Pydantic schemas, repository layer, and orchestrator in the options-tracker backend
type: project
---

The backend API layer follows these established conventions:

- All repositories accept a mocked `AsyncSession` — unit tests mock the session directly (no DB needed for unit tests).
- `EquityPositionResponse.underlying` maps from ORM field `EquityPosition.symbol` via `Field(alias="symbol")` with `populate_by_name=True` — this is intentional since the API exposes `underlying` but the DB column is `symbol`.
- `deduplicate_rows()` returns `list[DeduplicationResult]` (each has `.status`, `.row`, `.matched_upload_id`). There is no aggregate object — the orchestrator must sum counts manually.
- `ParsedRow.option_type` is `str | None` (raw string "CALL"/"PUT"), not the `OptionType` enum.
- The upload orchestrator bug (using nonexistent `.duplicate_count`/`.statuses` attributes on the dedup result) was fixed: orchestrator now iterates `dedup_results[i].status`.

**Why:** These were discovered during the first complete test pass (2026-04-01). Record to avoid re-discovering.

**How to apply:** When writing tests for orchestrator or schema layer, use str for `option_type` in `ParsedRow`, use `Field(alias=...)` for mismatched ORM/schema field names, and sum dedup statuses manually from the list.
