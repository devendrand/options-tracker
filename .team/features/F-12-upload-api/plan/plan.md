# F-12: Upload API Endpoints

**Feature:** F-12  
**Owner:** backend-tdd-api-dev  
**Status:** Pending plan  
**Depends on:** F-06 (Parser), F-07 (Classifier), F-08 (Dedup), F-09 (Matcher), F-10 (P&L)

---

## Open Question Resolutions Affecting This Feature

### OQ1 — Equity P&L in v0.1 (Resolved 2026-03-30)

**Resolution:** The upload processing pipeline must include equity P&L calculation as a **Should Have** step.

**Impact on `POST /api/v1/uploads` pipeline:**

The full pipeline sequence after CSV parsing and classification:
1. Parse → `ParsedTransaction` list
2. Classify → assign `TransactionCategory`
3. Deduplicate → mark `ACTIVE` / `DUPLICATE` / `POSSIBLE_DUPLICATE`
4. Match → create `OptionsPosition` + `OptionsPositionLeg` records (FIFO)
5. **Equity close matching** ← added by OQ1: match `EQUITY_SELL` against open `EquityPosition` lots (FIFO)
6. P&L calculation → compute realized P&L for newly closed options AND equity positions

**Upload summary response** must include equity position stats alongside options stats. The `rows_parsed`, `options_count`, `duplicate_count`, `possible_duplicate_count`, `parse_error_count`, and `internal_transfer_count` fields are unchanged. No new top-level fields required for equity in v0.1 — equity P&L is surfaced via the positions and P&L summary endpoints.

**Soft-delete cascade (`DELETE /api/v1/uploads/{id}`):**
- Must cascade soft-delete to both `OptionsPosition` AND `EquityPosition` records created from this upload
- Positions straddling two uploads (one leg from deleted upload, one from another): revert to `OPEN` for both position types
- Warning message about possible duplicate resurfacing applies to both position types
