---
name: Upload Orchestrator Matcher Wiring
description: How matcher/P&L/covered-call are wired into process_upload, and key edge cases handled
type: project
---

The upload orchestrator (`app/services/upload_orchestrator.py`) runs the full pipeline:
parse → classify → dedup → persist transactions → match → P&L → covered calls.

**Key design decisions:**

- `active_txns: list[tuple[int, Transaction]]` is built during the persistence loop — the int is the row_index in `parsed_rows` (needed to look up `categories`), the Transaction has UUIDs available at construction time (no flush needed).
- `_build_transaction_inputs()` must handle `option_type` being either `str` (freshly constructed) or `OptionType` enum (after DB roundtrip) — uses `isinstance(ot, OptionType)` check.
- For options transactions, `underlying = txn.symbol` — the symbol field stores the underlying ticker for both equity and options rows.
- `_persist_match_result()` deduplicates by `transaction_index` when building `LegData` for P&L — a single close transaction can appear in multiple `MatchedLeg` objects (scale-in: one close fills multiple open legs). Without dedup, commissions/amounts would be double-counted.
- Covered call detection uses only equity lots from the SAME upload batch (not queried from DB). Cross-upload covered-call re-evaluation is a future concern.
- Covered call check uses `net_qty = open_qty - close_qty` to correctly handle PARTIALLY_CLOSED positions.

**Why:** The matcher/P&L/covered_call services are all pure functions — they do no DB I/O. The orchestrator bridges them to persistence.

**How to apply:** When touching `process_upload`, all three post-transaction steps (matching, P&L, covered calls) are in `_persist_match_result`. No DB flushes happen inside that function — the caller flushes once after.
