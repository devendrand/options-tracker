# Options Tracker Smoke Test Suite

End-to-end validation of the deployed Options Tracker stack. Covers 12 test
categories across 60+ assertions derived from the F-19 test plan.

---

## Prerequisites

- Python 3.10+
- `requests` library: `pip install requests`
- A running Options Tracker stack (see below)

---

## Running the Tests

### 1. Start the stack

```bash
# From the project root
cp .env.example .env
docker compose up -d

# Verify all services are healthy
docker compose ps
# All three (db, backend, frontend) should show "healthy"
```

### 2. Run the smoke tests

```bash
# From the project root
cd smoke-tests
pip install -r requirements.txt
python run_smoke_tests.py
```

By default the script targets `http://localhost:8000`. To override:

```bash
# Via environment variable
SMOKE_BASE_URL=http://staging.example.com:8000 python run_smoke_tests.py

# Via positional argument
python run_smoke_tests.py http://staging.example.com:8000
```

### 3. Clean run (reset DB state)

The smoke tests are designed to self-clean via DELETE after each scenario.
For a guaranteed-clean run (e.g., after a failed run left orphaned data):

```bash
docker compose down -v
docker compose up -d
# Wait for healthy, then re-run
python run_smoke_tests.py
```

---

## Test Categories

| Category | Description | Test IDs |
|---|---|---|
| 1 — Infrastructure | Health endpoint, docs, 404 shape | SMOKE-INF-* |
| 2 — Covered Call | STO + BTC, equity coverage, P&L=248.70, is_covered_call | SMOKE-CC-* |
| 3 — Long Call Expiry | BTO + Option Expired, P&L=-250.65 | SMOKE-EXP-* |
| 4 — Assignment | STO PUT + Assigned, equity lot created at strike | SMOKE-ASN-* |
| 5 — Partial Close | STO 2 contracts + BTC 1 contract → PARTIALLY_CLOSED | SMOKE-PC-* |
| 6 — Equity Trades | EQUITY_BUY + EQUITY_SELL, remaining lot | SMOKE-EQ-* |
| 7 — Dividends/Transfers | DRIP pair + TRNSFR pair, internal_transfer_count=2 | SMOKE-DT-* |
| 8 — Deduplication | Same CSV uploaded twice → duplicate_count=3 | SMOKE-DUP-* |
| 9 — Soft Delete | DELETE cascade: upload → transactions → positions | SMOKE-DEL-* |
| 10 — P&L Summary | Year/month aggregation, numeric fields | SMOKE-PNL-* |
| 11 — Error Handling | .txt file, empty file, fake UUID, limit>500 | SMOKE-ERR-* |
| 12 — API Contract | Pagination defaults, response shapes | SMOKE-API-* |

---

## Fixture Files

Located in `smoke-tests/fixtures/`:

| File | Scenario | rows | options | Expected position |
|---|---|---|---|---|
| `covered_call.csv` | EQUITY_BUY(200 NVDA) + STO CALL + BTC CALL | 3 | 2 | NVDA CALL CLOSED, P&L=248.70, is_covered_call=true |
| `duplicate_upload.csv` | Identical copy of covered_call.csv | 3 | 2 | duplicate_count=3 on second upload |
| `long_call_expiry.csv` | BTO AAPL CALL + Option Expired | 2 | 2 | AAPL CALL EXPIRED, P&L=-250.65 |
| `assignment.csv` | STO TSLA PUT + Assigned | 2 | 2 | TSLA PUT ASSIGNED, equity lot created |
| `partial_close.csv` | STO SPY CALL (2 contracts) + BTC (1 contract) | 2 | 2 | SPY CALL PARTIALLY_CLOSED |
| `equity_trades.csv` | EQUITY_BUY(10 META) + EQUITY_SELL(5 META) | 2 | 0 | META equity OPEN (5 shares) |
| `dividends_transfers.csv` | 2 DIVIDEND rows + 2 TRNSFR Transfer rows | 4 | 0 | internal_transfer_count=2 |

---

## P&L Calculations Reference

These are the manually-computed P&L values verified by the smoke tests:

| Scenario | Formula | Expected P&L |
|---|---|---|
| Covered Call (NVDA) | 350.00 + (−100.00) − 0.65 − 0.65 | **$248.70** |
| Long Call Expiry (AAPL) | −250.00 + 0.00 − 0.65 − 0.00 | **−$250.65** |

---

## Go / No-Go Criteria

**All tests must pass** before promoting to any environment.
The script exits with code `0` on full pass, `1` on any failure.

The final output line will be either:
```
GO/NO-GO: GO
```
or:
```
GO/NO-GO: NO-GO
```

---

## CI Integration

To run smoke tests in GitHub Actions after `docker compose build`:

```yaml
smoke:
  needs: build
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: docker/setup-buildx-action@v3
    - name: Copy env
      run: cp .env.example .env
    - name: Start stack
      run: docker compose up -d
    - name: Wait for backend healthy
      run: |
        for i in $(seq 1 30); do
          curl -sf http://localhost:8000/health && break
          echo "Waiting... ($i)"
          sleep 5
        done
    - name: Install test deps
      run: pip install -r smoke-tests/requirements.txt
    - name: Run smoke tests
      run: python smoke-tests/run_smoke_tests.py
    - name: Tear down
      if: always()
      run: docker compose down -v
```

---

## Troubleshooting

**Connection refused**: Stack is not running or health check failed.
Run `docker compose ps` and check all services are `healthy`.

**duplicate_count mismatch**: Stale data from a prior run.
Run `docker compose down -v && docker compose up -d` for a clean database.

**P&L mismatch**: Covered call P&L (248.70) or expiry P&L (-250.65) wrong.
Check the upload fixture data and the P&L formula in `backend/app/services/pnl.py`.
