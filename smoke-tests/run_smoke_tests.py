#!/usr/bin/env python3
"""Options Tracker End-to-End Smoke Test Suite.

Validates the fully-deployed stack against all critical user journeys.
Targets a configurable base URL (default: http://localhost:8000).

Usage:
    python run_smoke_tests.py [BASE_URL]

    BASE_URL defaults to http://localhost:8000 or the SMOKE_BASE_URL env var.

Requirements:
    pip install requests

Each test prints PASS or FAIL with the assertion detail.
A summary at the end shows total pass/fail counts and exits non-zero on failure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed. Run: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
FIXTURES_DIR = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Test runner state
# ---------------------------------------------------------------------------

_pass_count = 0
_fail_count = 0
_current_section = ""


def section(name: str) -> None:
    global _current_section
    _current_section = name
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def ok(label: str) -> None:
    global _pass_count
    _pass_count += 1
    print(f"  \033[32mPASS\033[0m  {label}")


def fail(label: str, detail: str = "") -> None:
    global _fail_count
    _fail_count += 1
    msg = f"  \033[31mFAIL\033[0m  {label}"
    if detail:
        msg += f"\n        {detail}"
    print(msg)


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        ok(label)
    else:
        fail(label, detail)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def upload_csv(filename: str) -> requests.Response:
    """POST a CSV fixture to /api/v1/uploads."""
    path = FIXTURES_DIR / filename
    with open(path, "rb") as f:
        return requests.post(
            f"{BASE_URL}/api/v1/uploads",
            files={"file": (filename, f, "text/csv")},
            timeout=30,
        )


def get(path: str, **params: Any) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", params=params, timeout=10)


def delete(path: str) -> requests.Response:
    return requests.delete(f"{BASE_URL}{path}", timeout=10)


def find_position(positions: list[dict], underlying: str, option_type: str | None = None) -> dict | None:
    """Find the first matching position in a positions list."""
    for p in positions:
        if p.get("underlying") == underlying:
            if option_type is None or p.get("option_type") == option_type:
                return p
    return None


def get_options_positions() -> list[dict]:
    resp = get("/api/v1/positions", asset_type="options", limit=500)
    if resp.status_code != 200:
        return []
    return resp.json().get("options_items", [])


def get_equity_positions() -> list[dict]:
    resp = get("/api/v1/positions", asset_type="equity", limit=500)
    if resp.status_code != 200:
        return []
    return resp.json().get("equity_items", [])


# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------

_upload_ids_to_cleanup: list[str] = []


def track_upload(upload_id: str) -> None:
    _upload_ids_to_cleanup.append(upload_id)


def cleanup_all_uploads() -> None:
    for uid in _upload_ids_to_cleanup:
        try:
            delete(f"/api/v1/uploads/{uid}")
        except Exception:
            pass
    _upload_ids_to_cleanup.clear()


# ---------------------------------------------------------------------------
# CATEGORY 1: Infrastructure Health
# ---------------------------------------------------------------------------

def test_infrastructure() -> None:
    section("CATEGORY 1: Infrastructure Health")

    # SMOKE-INF-01: /health endpoint
    resp = get("/health")
    check(resp.status_code == 200, "SMOKE-INF-01: GET /health returns 200",
          f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        check(body.get("status") == "ok", "SMOKE-INF-01: /health body is {\"status\": \"ok\"}",
              f"body={body}")

    # SMOKE-INF-02: /docs (OpenAPI) accessible
    resp = get("/docs")
    check(resp.status_code == 200, "SMOKE-INF-02: GET /docs returns 200",
          f"status={resp.status_code}")

    # SMOKE-INF-03: Unknown route returns 404 JSON (not HTML)
    resp = get("/api/v1/nonexistent-route-xyz")
    check(resp.status_code == 404, "SMOKE-INF-03: Unknown route returns 404",
          f"status={resp.status_code}")
    check("application/json" in resp.headers.get("content-type", ""),
          "SMOKE-INF-03: Unknown route returns JSON body (not HTML)",
          f"content-type={resp.headers.get('content-type')}")

    # SMOKE-INF-04: API list endpoints return 200 on empty DB
    resp = get("/api/v1/uploads")
    check(resp.status_code == 200, "SMOKE-INF-04: GET /api/v1/uploads returns 200 on empty DB",
          f"status={resp.status_code}")

    resp = get("/api/v1/positions")
    check(resp.status_code == 200, "SMOKE-INF-04: GET /api/v1/positions returns 200 on empty DB",
          f"status={resp.status_code}")


# ---------------------------------------------------------------------------
# CATEGORY 2: Covered Call — STO + BTC (with equity position for coverage)
# ---------------------------------------------------------------------------

def test_covered_call() -> tuple[str, str]:
    """Upload covered_call.csv. Returns (upload_id, nvda_position_id)."""
    section("CATEGORY 2: Covered Call — STO + BTC")

    resp = upload_csv("covered_call.csv")
    check(resp.status_code == 201, "SMOKE-CC-01: POST covered_call.csv returns 201",
          f"status={resp.status_code}, body={resp.text[:200]}")

    if resp.status_code != 201:
        return "", ""

    body = resp.json()
    upload_id = body.get("id", "")
    track_upload(upload_id)

    # Upload summary counts
    check(body.get("row_count") == 3, "SMOKE-CC-02: row_count=3",
          f"row_count={body.get('row_count')}")
    check(body.get("options_count") == 2, "SMOKE-CC-03: options_count=2 (STO+BTC)",
          f"options_count={body.get('options_count')}")
    check(body.get("duplicate_count") == 0, "SMOKE-CC-04: duplicate_count=0",
          f"duplicate_count={body.get('duplicate_count')}")
    check(body.get("internal_transfer_count") == 0, "SMOKE-CC-05: internal_transfer_count=0",
          f"internal_transfer_count={body.get('internal_transfer_count')}")
    check(body.get("status") == "ACTIVE", "SMOKE-CC-06: upload status=ACTIVE",
          f"status={body.get('status')}")

    # GET /api/v1/uploads/{id}
    detail_resp = get(f"/api/v1/uploads/{upload_id}")
    check(detail_resp.status_code == 200, "SMOKE-CC-07: GET /api/v1/uploads/{id} returns 200",
          f"status={detail_resp.status_code}")
    if detail_resp.status_code == 200:
        detail = detail_resp.json()
        check(detail.get("transaction_count", 0) > 0, "SMOKE-CC-08: transaction_count>0 in detail",
              f"transaction_count={detail.get('transaction_count')}")

    # Transactions exist
    txn_resp = get("/api/v1/transactions", limit=100)
    check(txn_resp.status_code == 200, "SMOKE-CC-09: GET /api/v1/transactions returns 200",
          f"status={txn_resp.status_code}")

    # NVDA CALL position should be CLOSED
    positions = get_options_positions()
    nvda_pos = find_position(positions, "NVDA", "CALL")
    check(nvda_pos is not None, "SMOKE-CC-10: NVDA CALL position exists",
          f"options_items={[p.get('underlying') for p in positions]}")

    pos_id = ""
    if nvda_pos:
        pos_id = nvda_pos.get("id", "")
        check(nvda_pos.get("status") == "CLOSED", "SMOKE-CC-11: NVDA CALL status=CLOSED",
              f"status={nvda_pos.get('status')}")
        check(nvda_pos.get("is_covered_call") is True, "SMOKE-CC-12: is_covered_call=True (200 shares NVDA held)",
              f"is_covered_call={nvda_pos.get('is_covered_call')}")
        check(nvda_pos.get("direction") == "SHORT", "SMOKE-CC-13: direction=SHORT (STO)",
              f"direction={nvda_pos.get('direction')}")

        # P&L = open_amount + close_amount - commissions = 350.00 + (-100.00) - 0.65 - 0.65 = 248.70
        pnl = nvda_pos.get("realized_pnl")
        check(pnl is not None, "SMOKE-CC-14: realized_pnl is not None",
              f"realized_pnl={pnl}")
        if pnl is not None:
            check(float(pnl) == 248.70, "SMOKE-CC-14: realized_pnl=248.70 (350-100-0.65-0.65)",
                  f"realized_pnl={pnl}")

        # Position detail with legs
        detail_resp = get(f"/api/v1/positions/{pos_id}")
        check(detail_resp.status_code == 200, "SMOKE-CC-15: GET /api/v1/positions/{id} returns 200",
              f"status={detail_resp.status_code}")
        if detail_resp.status_code == 200:
            detail = detail_resp.json()
            legs = detail.get("legs", [])
            check(len(legs) == 2, "SMOKE-CC-16: position has 2 legs (open+close)",
                  f"len(legs)={len(legs)}")
            check(detail.get("total_realized_pnl") is not None,
                  "SMOKE-CC-17: total_realized_pnl present in detail",
                  f"total_realized_pnl={detail.get('total_realized_pnl')}")

    # Equity position for NVDA (200 shares)
    equity_positions = get_equity_positions()
    nvda_equity = find_position(equity_positions, "NVDA")
    check(nvda_equity is not None, "SMOKE-CC-18: NVDA equity position created (200 shares)",
          f"equity_items={[p.get('underlying') for p in equity_positions]}")
    if nvda_equity:
        check(float(nvda_equity.get("quantity", 0)) == 200.0, "SMOKE-CC-19: NVDA equity quantity=200",
              f"quantity={nvda_equity.get('quantity')}")

    return upload_id, pos_id


# ---------------------------------------------------------------------------
# CATEGORY 3: Long Call + Expiry (OPTIONS_BUY_TO_OPEN + OPTIONS_EXPIRED)
# ---------------------------------------------------------------------------

def test_long_call_expiry() -> str:
    """Upload long_call_expiry.csv. Returns upload_id."""
    section("CATEGORY 3: Long Call + Expiry (BTO + Option Expired)")

    resp = upload_csv("long_call_expiry.csv")
    check(resp.status_code == 201, "SMOKE-EXP-01: POST long_call_expiry.csv returns 201",
          f"status={resp.status_code}, body={resp.text[:200]}")

    if resp.status_code != 201:
        return ""

    body = resp.json()
    upload_id = body.get("id", "")
    track_upload(upload_id)

    check(body.get("row_count") == 2, "SMOKE-EXP-02: row_count=2",
          f"row_count={body.get('row_count')}")
    check(body.get("options_count") == 2, "SMOKE-EXP-03: options_count=2 (BTO+Expired)",
          f"options_count={body.get('options_count')}")

    # AAPL CALL position should be EXPIRED
    positions = get_options_positions()
    aapl_pos = find_position(positions, "AAPL", "CALL")
    check(aapl_pos is not None, "SMOKE-EXP-04: AAPL CALL position exists",
          f"options_items={[p.get('underlying') for p in positions]}")

    if aapl_pos:
        check(aapl_pos.get("status") == "EXPIRED", "SMOKE-EXP-05: AAPL CALL status=EXPIRED",
              f"status={aapl_pos.get('status')}")
        check(aapl_pos.get("direction") == "LONG", "SMOKE-EXP-06: direction=LONG (BTO)",
              f"direction={aapl_pos.get('direction')}")

        # P&L = open_amount + close_amount - commissions = -250.00 + 0.00 - 0.65 - 0.00 = -250.65
        pnl = aapl_pos.get("realized_pnl")
        check(pnl is not None, "SMOKE-EXP-07: realized_pnl is not None for expired position",
              f"realized_pnl={pnl}")
        if pnl is not None:
            check(float(pnl) == -250.65, "SMOKE-EXP-07: realized_pnl=-250.65 (-250+0-0.65-0)",
                  f"realized_pnl={pnl}")

    return upload_id


# ---------------------------------------------------------------------------
# CATEGORY 4: Assignment (STO PUT + Assigned)
# ---------------------------------------------------------------------------

def test_assignment() -> str:
    """Upload assignment.csv. Returns upload_id."""
    section("CATEGORY 4: Assignment (Sold Short PUT + Assigned)")

    resp = upload_csv("assignment.csv")
    check(resp.status_code == 201, "SMOKE-ASN-01: POST assignment.csv returns 201",
          f"status={resp.status_code}, body={resp.text[:200]}")

    if resp.status_code != 201:
        return ""

    body = resp.json()
    upload_id = body.get("id", "")
    track_upload(upload_id)

    check(body.get("row_count") == 2, "SMOKE-ASN-02: row_count=2",
          f"row_count={body.get('row_count')}")
    check(body.get("options_count") == 2, "SMOKE-ASN-03: options_count=2 (STO+Assigned)",
          f"options_count={body.get('options_count')}")

    # TSLA PUT position should be ASSIGNED
    positions = get_options_positions()
    tsla_pos = find_position(positions, "TSLA", "PUT")
    check(tsla_pos is not None, "SMOKE-ASN-04: TSLA PUT position exists",
          f"options_items={[p.get('underlying') for p in positions]}")

    if tsla_pos:
        check(tsla_pos.get("status") == "ASSIGNED", "SMOKE-ASN-05: TSLA PUT status=ASSIGNED",
              f"status={tsla_pos.get('status')}")
        check(tsla_pos.get("direction") == "SHORT", "SMOKE-ASN-06: direction=SHORT (STO)",
              f"direction={tsla_pos.get('direction')}")

    # Equity position for TSLA created via assignment (100 shares at $250 strike)
    equity_positions = get_equity_positions()
    tsla_equity = find_position(equity_positions, "TSLA")
    check(tsla_equity is not None, "SMOKE-ASN-07: TSLA equity position created via assignment",
          f"equity_items={[p.get('underlying') for p in equity_positions]}")
    if tsla_equity:
        check(tsla_equity.get("source") == "ASSIGNMENT",
              "SMOKE-ASN-08: TSLA equity source=ASSIGNMENT",
              f"source={tsla_equity.get('source')}")
        check(float(tsla_equity.get("quantity", 0)) == 100.0,
              "SMOKE-ASN-09: TSLA equity quantity=100 (1 contract × 100 shares)",
              f"quantity={tsla_equity.get('quantity')}")
        check(float(tsla_equity.get("cost_basis_per_share", 0)) == 250.0,
              "SMOKE-ASN-10: TSLA cost_basis_per_share=250.00 (strike price)",
              f"cost_basis_per_share={tsla_equity.get('cost_basis_per_share')}")

    return upload_id


# ---------------------------------------------------------------------------
# CATEGORY 5: Partial Close (STO 2 contracts + BTC 1 contract)
# ---------------------------------------------------------------------------

def test_partial_close() -> str:
    """Upload partial_close.csv. Returns upload_id."""
    section("CATEGORY 5: Partial Close (STO 2 contracts + BTC 1 contract)")

    resp = upload_csv("partial_close.csv")
    check(resp.status_code == 201, "SMOKE-PC-01: POST partial_close.csv returns 201",
          f"status={resp.status_code}, body={resp.text[:200]}")

    if resp.status_code != 201:
        return ""

    body = resp.json()
    upload_id = body.get("id", "")
    track_upload(upload_id)

    check(body.get("row_count") == 2, "SMOKE-PC-02: row_count=2",
          f"row_count={body.get('row_count')}")
    check(body.get("options_count") == 2, "SMOKE-PC-03: options_count=2",
          f"options_count={body.get('options_count')}")

    # SPY CALL position should be PARTIALLY_CLOSED
    positions = get_options_positions()
    spy_pos = find_position(positions, "SPY", "CALL")
    check(spy_pos is not None, "SMOKE-PC-04: SPY CALL position exists",
          f"options_items={[p.get('underlying') for p in positions]}")

    if spy_pos:
        check(spy_pos.get("status") == "PARTIALLY_CLOSED",
              "SMOKE-PC-05: SPY CALL status=PARTIALLY_CLOSED",
              f"status={spy_pos.get('status')}")

        # P&L should be non-None (partial close has computed P&L for matched portion)
        pnl = spy_pos.get("realized_pnl")
        check(pnl is not None, "SMOKE-PC-06: realized_pnl is not None for partially closed position",
              f"realized_pnl={pnl}")

        # Position detail should have 2 legs
        pos_id = spy_pos.get("id", "")
        detail_resp = get(f"/api/v1/positions/{pos_id}")
        if detail_resp.status_code == 200:
            detail = detail_resp.json()
            legs = detail.get("legs", [])
            check(len(legs) == 2, "SMOKE-PC-07: position has 2 legs (1 open + 1 close)",
                  f"len(legs)={len(legs)}")
            leg_roles = [leg.get("leg_role") for leg in legs]
            check("OPEN" in leg_roles, "SMOKE-PC-08: at least one OPEN leg present",
                  f"leg_roles={leg_roles}")
            check("CLOSE" in leg_roles, "SMOKE-PC-09: at least one CLOSE leg present",
                  f"leg_roles={leg_roles}")

    return upload_id


# ---------------------------------------------------------------------------
# CATEGORY 6: Equity Trades (BUY + SELL)
# ---------------------------------------------------------------------------

def test_equity_trades() -> str:
    """Upload equity_trades.csv. Returns upload_id."""
    section("CATEGORY 6: Equity Trades (EQUITY_BUY + EQUITY_SELL)")

    resp = upload_csv("equity_trades.csv")
    check(resp.status_code == 201, "SMOKE-EQ-01: POST equity_trades.csv returns 201",
          f"status={resp.status_code}, body={resp.text[:200]}")

    if resp.status_code != 201:
        return ""

    body = resp.json()
    upload_id = body.get("id", "")
    track_upload(upload_id)

    check(body.get("row_count") == 2, "SMOKE-EQ-02: row_count=2",
          f"row_count={body.get('row_count')}")
    check(body.get("options_count") == 0, "SMOKE-EQ-03: options_count=0 (equity only)",
          f"options_count={body.get('options_count')}")
    check(body.get("internal_transfer_count") == 0, "SMOKE-EQ-04: internal_transfer_count=0",
          f"internal_transfer_count={body.get('internal_transfer_count')}")

    # META equity position: 10 bought, 5 sold → 5 remaining (OPEN)
    equity_positions = get_equity_positions()
    meta_equity = find_position(equity_positions, "META")
    check(meta_equity is not None, "SMOKE-EQ-05: META equity position exists",
          f"equity_items={[p.get('underlying') for p in equity_positions]}")
    if meta_equity:
        check(meta_equity.get("status") == "OPEN",
              "SMOKE-EQ-06: META equity status=OPEN (5 shares remaining)",
              f"status={meta_equity.get('status')}")
        check(float(meta_equity.get("quantity", 0)) == 5.0,
              "SMOKE-EQ-07: META equity quantity=5 (10 bought - 5 sold)",
              f"quantity={meta_equity.get('quantity')}")
        check(float(meta_equity.get("cost_basis_per_share", 0)) == 500.0,
              "SMOKE-EQ-08: META cost_basis_per_share=500.00",
              f"cost_basis_per_share={meta_equity.get('cost_basis_per_share')}")

    return upload_id


# ---------------------------------------------------------------------------
# CATEGORY 7: Dividends + Internal Transfers
# ---------------------------------------------------------------------------

def test_dividends_transfers() -> str:
    """Upload dividends_transfers.csv. Returns upload_id."""
    section("CATEGORY 7: Dividends + Internal Transfers")

    resp = upload_csv("dividends_transfers.csv")
    check(resp.status_code == 201, "SMOKE-DT-01: POST dividends_transfers.csv returns 201",
          f"status={resp.status_code}, body={resp.text[:200]}")

    if resp.status_code != 201:
        return ""

    body = resp.json()
    upload_id = body.get("id", "")
    track_upload(upload_id)

    check(body.get("row_count") == 4, "SMOKE-DT-02: row_count=4 (2 dividends + 2 transfers)",
          f"row_count={body.get('row_count')}")
    check(body.get("options_count") == 0, "SMOKE-DT-03: options_count=0",
          f"options_count={body.get('options_count')}")
    check(body.get("internal_transfer_count") == 2,
          "SMOKE-DT-04: internal_transfer_count=2 (both TRNSFR rows)",
          f"internal_transfer_count={body.get('internal_transfer_count')}")

    return upload_id


# ---------------------------------------------------------------------------
# CATEGORY 8: Deduplication
# ---------------------------------------------------------------------------

def test_deduplication(covered_call_upload_id: str) -> str:
    """Upload duplicate_upload.csv (same content as covered_call.csv).

    covered_call_upload_id must already be in the DB.
    Returns upload_id of the duplicate upload.
    """
    section("CATEGORY 8: Deduplication (duplicate_upload.csv = covered_call.csv)")

    if not covered_call_upload_id:
        fail("SMOKE-DUP-01: Skipped — covered_call upload_id not available")
        return ""

    resp = upload_csv("duplicate_upload.csv")
    check(resp.status_code == 201, "SMOKE-DUP-01: POST duplicate_upload.csv returns 201",
          f"status={resp.status_code}, body={resp.text[:200]}")

    if resp.status_code != 201:
        return ""

    body = resp.json()
    upload_id = body.get("id", "")
    track_upload(upload_id)

    check(body.get("row_count") == 3, "SMOKE-DUP-02: row_count=3",
          f"row_count={body.get('row_count')}")
    check(body.get("duplicate_count") == 3,
          "SMOKE-DUP-03: duplicate_count=3 (all 3 rows are exact duplicates)",
          f"duplicate_count={body.get('duplicate_count')}")
    check(body.get("options_count") == 2, "SMOKE-DUP-04: options_count=2 counted even for duplicates",
          f"options_count={body.get('options_count')}")

    return upload_id


# ---------------------------------------------------------------------------
# CATEGORY 9: Soft Delete + Cascade
# ---------------------------------------------------------------------------

def test_soft_delete(upload_id: str, fixture_label: str = "upload") -> None:
    """DELETE an upload and verify cascade behavior."""
    section(f"CATEGORY 9: Soft Delete + Cascade ({fixture_label})")

    if not upload_id:
        fail(f"SMOKE-DEL-01: Skipped — {fixture_label} upload_id not available")
        return

    # Capture transactions count before delete
    txn_before = get("/api/v1/transactions", limit=500)
    txn_count_before = len(txn_before.json().get("items", [])) if txn_before.status_code == 200 else 0

    resp = delete(f"/api/v1/uploads/{upload_id}")
    check(resp.status_code == 200, "SMOKE-DEL-01: DELETE /api/v1/uploads/{id} returns 200",
          f"status={resp.status_code}")

    if resp.status_code == 200:
        body = resp.json()
        check(body.get("status") == "SOFT_DELETED",
              "SMOKE-DEL-02: delete response status=SOFT_DELETED",
              f"status={body.get('status')}")
        check("warning" in body,
              "SMOKE-DEL-03: delete response includes warning field",
              f"body keys={list(body.keys())}")

    # Re-GET the deleted upload → should be 404
    resp = get(f"/api/v1/uploads/{upload_id}")
    check(resp.status_code == 404,
          "SMOKE-DEL-04: GET deleted upload returns 404",
          f"status={resp.status_code}")

    # Transactions from deleted upload should no longer appear
    txn_after = get("/api/v1/transactions", limit=500)
    txn_count_after = len(txn_after.json().get("items", [])) if txn_after.status_code == 200 else 0
    check(txn_count_after < txn_count_before,
          "SMOKE-DEL-05: transaction count decreases after soft-delete cascade",
          f"before={txn_count_before}, after={txn_count_after}")

    # Remove from cleanup list (already deleted)
    if upload_id in _upload_ids_to_cleanup:
        _upload_ids_to_cleanup.remove(upload_id)


# ---------------------------------------------------------------------------
# CATEGORY 10: P&L Summary
# ---------------------------------------------------------------------------

def test_pnl_summary() -> None:
    """Verify GET /api/v1/pnl/summary returns valid data."""
    section("CATEGORY 10: P&L Summary")

    # Default (year period, all types)
    resp = get("/api/v1/pnl/summary")
    check(resp.status_code == 200, "SMOKE-PNL-01: GET /api/v1/pnl/summary returns 200",
          f"status={resp.status_code}")

    if resp.status_code != 200:
        return

    body = resp.json()
    check("period" in body, "SMOKE-PNL-02: response has 'period' field",
          f"body keys={list(body.keys())}")
    check("items" in body, "SMOKE-PNL-03: response has 'items' field",
          f"body keys={list(body.keys())}")
    check(isinstance(body.get("items"), list), "SMOKE-PNL-04: items is a list",
          f"items type={type(body.get('items'))}")

    items = body.get("items", [])
    # Verify numeric fields
    for item in items:
        check(
            isinstance(item.get("options_pnl"), (int, float, str)),
            f"SMOKE-PNL-05: options_pnl is numeric for period {item.get('period_label')}",
            f"options_pnl={item.get('options_pnl')}"
        )

    # Check for NVDA P&L entry (covered call was closed: P&L=248.70)
    nvda_items = [i for i in items if "NVDA" in str(i.get("period_label", ""))]
    # period_label format is not per-symbol; check totals
    # The P&L summary uses period_label (year/month) not per symbol
    check(len(items) > 0, "SMOKE-PNL-06: P&L summary has at least one period entry",
          f"items={items}")

    # Month period
    resp_month = get("/api/v1/pnl/summary", period="month")
    check(resp_month.status_code == 200, "SMOKE-PNL-07: GET /api/v1/pnl/summary?period=month returns 200",
          f"status={resp_month.status_code}")

    if resp_month.status_code == 200:
        check(resp_month.json().get("period") == "month",
              "SMOKE-PNL-08: month summary period='month'",
              f"period={resp_month.json().get('period')}")

    # options-only filter
    resp_opts = get("/api/v1/pnl/summary", type="options")
    check(resp_opts.status_code == 200, "SMOKE-PNL-09: GET /api/v1/pnl/summary?type=options returns 200",
          f"status={resp_opts.status_code}")


# ---------------------------------------------------------------------------
# CATEGORY 11: Error Handling
# ---------------------------------------------------------------------------

def test_error_handling() -> None:
    section("CATEGORY 11: Error Handling and Validation")

    # SMOKE-ERR-01: Upload a .txt file (not CSV)
    resp = requests.post(
        f"{BASE_URL}/api/v1/uploads",
        files={"file": ("test.txt", b"this is not a csv file", "text/plain")},
        timeout=10,
    )
    check(resp.status_code in (400, 422),
          "SMOKE-ERR-01: POST .txt file returns 400 or 422",
          f"status={resp.status_code}")

    # SMOKE-ERR-02: Upload an empty CSV file
    resp = requests.post(
        f"{BASE_URL}/api/v1/uploads",
        files={"file": ("empty.csv", b"", "text/csv")},
        timeout=10,
    )
    check(resp.status_code in (400, 422),
          "SMOKE-ERR-02: POST empty .csv returns 400 or 422",
          f"status={resp.status_code}")

    # SMOKE-ERR-03: GET non-existent upload UUID
    fake_uuid = "00000000-0000-0000-0000-000000000001"
    resp = get(f"/api/v1/uploads/{fake_uuid}")
    check(resp.status_code == 404,
          "SMOKE-ERR-03: GET /api/v1/uploads/{fake_uuid} returns 404",
          f"status={resp.status_code}")
    check("application/json" in resp.headers.get("content-type", ""),
          "SMOKE-ERR-03: 404 response is JSON",
          f"content-type={resp.headers.get('content-type')}")

    # SMOKE-ERR-04: GET non-existent position UUID
    resp = get(f"/api/v1/positions/{fake_uuid}")
    check(resp.status_code == 404,
          "SMOKE-ERR-04: GET /api/v1/positions/{fake_uuid} returns 404",
          f"status={resp.status_code}")

    # SMOKE-ERR-05: DELETE non-existent upload UUID
    resp = delete(f"/api/v1/uploads/{fake_uuid}")
    check(resp.status_code == 404,
          "SMOKE-ERR-05: DELETE /api/v1/uploads/{fake_uuid} returns 404",
          f"status={resp.status_code}")

    # SMOKE-ERR-06: Exceeds max limit (limit=501 > 500)
    resp = get("/api/v1/transactions", limit=501)
    check(resp.status_code == 422,
          "SMOKE-ERR-06: GET /api/v1/transactions?limit=501 returns 422",
          f"status={resp.status_code}")

    # SMOKE-ERR-07: POST with no file field
    resp = requests.post(
        f"{BASE_URL}/api/v1/uploads",
        data={"not_file": "something"},
        timeout=10,
    )
    check(resp.status_code == 422,
          "SMOKE-ERR-07: POST /api/v1/uploads with missing file field returns 422",
          f"status={resp.status_code}")


# ---------------------------------------------------------------------------
# CATEGORY 12: API Contract and Pagination
# ---------------------------------------------------------------------------

def test_api_contract() -> None:
    section("CATEGORY 12: API Contract and Pagination")

    # Transactions: default pagination
    resp = get("/api/v1/transactions")
    check(resp.status_code == 200, "SMOKE-API-01: GET /api/v1/transactions returns 200",
          f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        check("items" in body, "SMOKE-API-01: transactions response has 'items'",
              f"keys={list(body.keys())}")
        check("total" in body, "SMOKE-API-01: transactions response has 'total'",
              f"keys={list(body.keys())}")
        check(body.get("offset") == 0, "SMOKE-API-02: default offset=0",
              f"offset={body.get('offset')}")
        check(body.get("limit") == 100, "SMOKE-API-02: default limit=100",
              f"limit={body.get('limit')}")

    # Positions at boundary limit=500
    resp = get("/api/v1/positions", limit=500)
    check(resp.status_code == 200, "SMOKE-API-03: GET /api/v1/positions?limit=500 returns 200",
          f"status={resp.status_code}")

    # Positions response shape
    if resp.status_code == 200:
        body = resp.json()
        check("options_items" in body, "SMOKE-API-04: positions response has 'options_items'",
              f"keys={list(body.keys())}")
        check("equity_items" in body, "SMOKE-API-04: positions response has 'equity_items'",
              f"keys={list(body.keys())}")
        check("total" in body, "SMOKE-API-04: positions response has 'total'",
              f"keys={list(body.keys())}")

    # Uploads list response shape
    resp = get("/api/v1/uploads")
    check(resp.status_code == 200, "SMOKE-API-05: GET /api/v1/uploads returns 200",
          f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        check("items" in body, "SMOKE-API-05: uploads response has 'items'",
              f"keys={list(body.keys())}")
        for item in body.get("items", []):
            required_fields = {"id", "filename", "broker", "status", "row_count",
                               "options_count", "duplicate_count"}
            missing = required_fields - set(item.keys())
            check(len(missing) == 0,
                  f"SMOKE-API-06: upload item has all required fields",
                  f"missing={missing}")
            break  # Only check first item


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\nOptions Tracker Smoke Test Suite")
    print(f"Target: {BASE_URL}")
    print(f"Fixtures: {FIXTURES_DIR}")

    # Verify fixtures exist
    required_fixtures = [
        "covered_call.csv", "duplicate_upload.csv", "long_call_expiry.csv",
        "assignment.csv", "partial_close.csv", "equity_trades.csv",
        "dividends_transfers.csv",
    ]
    missing = [f for f in required_fixtures if not (FIXTURES_DIR / f).exists()]
    if missing:
        print(f"\nERROR: Missing fixture files: {missing}")
        sys.exit(1)

    # Run test categories
    test_infrastructure()
    covered_call_id, _ = test_covered_call()
    test_long_call_expiry()
    test_assignment()
    test_partial_close()
    test_equity_trades()
    test_dividends_transfers()
    test_deduplication(covered_call_id)
    test_pnl_summary()
    test_error_handling()
    test_api_contract()

    # Soft-delete test using covered_call upload
    test_soft_delete(covered_call_id, "covered_call")

    # Cleanup remaining uploads
    section("Cleanup")
    if _upload_ids_to_cleanup:
        print(f"  Cleaning up {len(_upload_ids_to_cleanup)} remaining upload(s)...")
        cleanup_all_uploads()
        ok("Cleanup: all uploads deleted")
    else:
        ok("Cleanup: nothing to clean up")

    # Summary
    total = _pass_count + _fail_count
    print(f"\n{'='*60}")
    print(f"  RESULTS: {_pass_count}/{total} passed")
    if _fail_count > 0:
        print(f"  \033[31m{_fail_count} FAILED\033[0m")
        print(f"  \033[31mGO/NO-GO: NO-GO\033[0m")
    else:
        print(f"  \033[32mAll tests passed\033[0m")
        print(f"  \033[32mGO/NO-GO: GO\033[0m")
    print(f"{'='*60}\n")

    sys.exit(0 if _fail_count == 0 else 1)


if __name__ == "__main__":
    main()
