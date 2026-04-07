---
name: Frontend-Backend API Contract Mismatches
description: API contract issues found across reviews — includes resolved (F-15/F-18) and active (final review) gaps
type: project
---

## Resolved Issues (F-15 to F-18 implementation fixed all of these)

The following were flagged in the F-15 to F-18 plan review on 2026-04-01 and have been resolved:
- Upload model: `created_at` → `uploaded_at`, removed `updated_at`/`error_message`, added `possible_duplicate_count`/`internal_transfer_count`
- Upload service: now returns `UploadListResponse` (not `Upload[]`)
- Position model: `leg_type` → `leg_role`, `OptionsPositionLeg` now has `price/amount/commission/trade_date`, `PositionListResponse` uses `options_items`/`equity_items`
- PnL model: `PnlPeriodEntry` now has `options_pnl/equity_pnl/total_pnl`, `PnlSummary.items` (not `.entries`)

---

## Active Issue — Found in Final Review 2026-04-01

### `EquityPositionResponse.underlying` alias causes JSON contract mismatch

**Backend schema:** `underlying: str = Field(alias="symbol")`
**FastAPI behavior:** Serializes response with `by_alias=True` → JSON key is `"symbol"`
**Frontend expects:** `EquityPosition.underlying: string`
**Result:** Equity `underlying` field is always `undefined` in the frontend at runtime.

**Why not caught:** Unit tests checked Python attribute access and response counts only — no test asserted `data["equity_items"][0]["symbol"]`. Smoke tests check `p.get("underlying")` which would fail against a live server, but smoke tests are not in the CI gate.

**Required fix:** Remove `Field(alias="symbol")` from `EquityPositionResponse`; use `symbol: str` as the field name. Update frontend `EquityPosition.underlying → symbol`. Add JSON key assertion to API router test.

**Why:** Needed for production promotion of v0.1. Task #11 (F-20 deployment) is blocked on this fix.
