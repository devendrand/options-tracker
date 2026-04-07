---
name: F-19 Smoke Test Suite
description: Location, structure, and execution details of the smoke test suite for Options Tracker
type: project
---

Smoke test suite implemented 2026-04-01.

**Location:** `smoke-tests/` at project root
- `run_smoke_tests.py` — main Python script, uses `requests`
- `requirements.txt` — `requests>=2.31.0`
- `fixtures/` — 7 CSV fixture files

**How to run:**
```bash
cd smoke-tests && pip install -r requirements.txt
python run_smoke_tests.py [BASE_URL]
# BASE_URL defaults to http://localhost:8000 or $SMOKE_BASE_URL
```

**Fixtures → expected outcomes:**
- `covered_call.csv`: 3 rows, options_count=2, NVDA CALL CLOSED, P&L=248.70, is_covered_call=true
- `duplicate_upload.csv`: identical to covered_call.csv, duplicate_count=3 on second upload
- `long_call_expiry.csv`: 2 rows, AAPL CALL EXPIRED, P&L=-250.65
- `assignment.csv`: 2 rows, TSLA PUT ASSIGNED, equity lot (100 shares at $250)
- `partial_close.csv`: 2 rows, SPY CALL PARTIALLY_CLOSED
- `equity_trades.csv`: 2 rows, META equity OPEN (5 shares remaining)
- `dividends_transfers.csv`: 4 rows, internal_transfer_count=2

**12 test categories, 60+ assertions.** Exits 0 on full pass, 1 on any failure.

**Why:** All 12 categories must pass (GO/NO-GO: GO) before promoting to any environment.

**How to apply:** Run after `docker compose up -d` and all services are healthy. Use `docker compose down -v && docker compose up -d` for clean state before a run.
