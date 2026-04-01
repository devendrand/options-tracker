"""Unit tests for the P&L calculation service (app.services.pnl).

Test order follows the Red → Green → Refactor TDD cycle:
- Tests are written first; pnl.py does not exist yet.
- All tests must pass after implementation with no regressions.

Coverage targets: 100% line + branch.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services.pnl import (
    EquityPnlResult,
    LegData,
    OptionsPnlResult,
    PnlSummaryEntry,
    aggregate_pnl,
    calculate_equity_pnl,
    calculate_options_pnl,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_leg(amount: str, commission: str = "0.00", quantity: str = "1") -> LegData:
    """Convenience factory for an open options leg."""
    return LegData(
        quantity=Decimal(quantity),
        price=Decimal("0.00"),  # price not used in current formula; amount is pre-computed
        amount=Decimal(amount),
        commission=Decimal(commission),
        is_open=True,
    )


def _close_leg(amount: str, commission: str = "0.00", quantity: str = "1") -> LegData:
    """Convenience factory for a close options leg."""
    return LegData(
        quantity=Decimal(quantity),
        price=Decimal("0.00"),
        amount=Decimal(amount),
        commission=Decimal(commission),
        is_open=False,
    )


# ---------------------------------------------------------------------------
# Options P&L — Scenario 1: Covered call (STO + BTC)
# STO: amount=+200.00, commission=0.65
# BTC: amount=-150.00, commission=0.65
# P&L = 200 + (-150) - 0.65 - 0.65 = 48.70
# ---------------------------------------------------------------------------


def test_calculate_options_pnl_covered_call_positive_pnl() -> None:
    """STO premium received then BTC to close — net positive P&L."""
    legs = [
        _open_leg(amount="200.00", commission="0.65"),
        _close_leg(amount="-150.00", commission="0.65"),
    ]
    result = calculate_options_pnl(legs)

    assert result.realized_pnl == Decimal("48.70")
    assert result.open_amount == Decimal("200.00")
    assert result.close_amount == Decimal("-150.00")
    assert result.total_commission == Decimal("1.30")


# ---------------------------------------------------------------------------
# Scenario 2: Long call expired worthless
# BTO: amount=-300.00, commission=0.65
# Expired: amount=0.00, commission=0.00
# P&L = -300 + 0 - 0.65 - 0.00 = -300.65
# ---------------------------------------------------------------------------


def test_calculate_options_pnl_long_call_expired_worthless() -> None:
    """BTO then expired worthless — full premium lost."""
    legs = [
        _open_leg(amount="-300.00", commission="0.65"),
        _close_leg(amount="0.00", commission="0.00"),
    ]
    result = calculate_options_pnl(legs)

    assert result.realized_pnl == Decimal("-300.65")
    assert result.open_amount == Decimal("-300.00")
    assert result.close_amount == Decimal("0.00")
    assert result.total_commission == Decimal("0.65")


# ---------------------------------------------------------------------------
# Scenario 3: Position still fully open (no close legs) → realized_pnl = None
# ---------------------------------------------------------------------------


def test_calculate_options_pnl_no_close_legs_returns_none_realized() -> None:
    """Open position with no close legs must return realized_pnl=None."""
    legs = [
        _open_leg(amount="-500.00", commission="1.30"),
    ]
    result = calculate_options_pnl(legs)

    assert result.realized_pnl is None
    assert result.open_amount == Decimal("-500.00")
    assert result.close_amount == Decimal("0.00")
    assert result.total_commission == Decimal("1.30")


# ---------------------------------------------------------------------------
# Scenario 4: Partial close — only closed portion contributes
# Two open legs (scale-in), one close leg covering 1 of 2 contracts.
# The formula uses the actual amounts stored on the legs (already reflect
# partial quantities at write time), so we pass matching amounts directly.
# ---------------------------------------------------------------------------


def test_calculate_options_pnl_partial_close_uses_actual_amounts() -> None:
    """Partial close: realized_pnl computed from actual open+close amounts present."""
    # Open 2 contracts, close only 1 — caller passes only the matched leg amounts
    legs = [
        _open_leg(amount="100.00", commission="0.65", quantity="1"),  # matched open portion
        _close_leg(amount="-60.00", commission="0.65", quantity="1"),
    ]
    result = calculate_options_pnl(legs)

    # P&L = 100 + (-60) - 0.65 - 0.65 = 38.70
    assert result.realized_pnl == Decimal("38.70")
    assert result.open_amount == Decimal("100.00")
    assert result.close_amount == Decimal("-60.00")
    assert result.total_commission == Decimal("1.30")


# ---------------------------------------------------------------------------
# Scenario 5: Multiple open legs (scale-in) + single close leg
# Open leg 1: amount=+100.00, commission=0.65
# Open leg 2: amount=+80.00, commission=0.65
# Close leg:  amount=-120.00, commission=0.65
# P&L = (100 + 80) + (-120) - (0.65+0.65+0.65) = 60 - 1.95 = 58.05
# ---------------------------------------------------------------------------


def test_calculate_options_pnl_multiple_open_legs_single_close() -> None:
    """Scale-in (two open legs) followed by single close — all amounts summed."""
    legs = [
        _open_leg(amount="100.00", commission="0.65"),
        _open_leg(amount="80.00", commission="0.65"),
        _close_leg(amount="-120.00", commission="0.65"),
    ]
    result = calculate_options_pnl(legs)

    assert result.realized_pnl == Decimal("58.05")
    assert result.open_amount == Decimal("180.00")
    assert result.close_amount == Decimal("-120.00")
    assert result.total_commission == Decimal("1.95")


# ---------------------------------------------------------------------------
# Scenario 6: Zero commission trades
# ---------------------------------------------------------------------------


def test_calculate_options_pnl_zero_commission() -> None:
    """Trades with no commissions: P&L = open_amount + close_amount."""
    legs = [
        _open_leg(amount="500.00", commission="0.00"),
        _close_leg(amount="-200.00", commission="0.00"),
    ]
    result = calculate_options_pnl(legs)

    assert result.realized_pnl == Decimal("300.00")
    assert result.total_commission == Decimal("0.00")


# ---------------------------------------------------------------------------
# Scenario — empty legs list: no open, no close
# ---------------------------------------------------------------------------


def test_calculate_options_pnl_empty_legs() -> None:
    """No legs at all: all zeros, realized_pnl=None (no close legs)."""
    result = calculate_options_pnl([])

    assert result.realized_pnl is None
    assert result.open_amount == Decimal("0.00")
    assert result.close_amount == Decimal("0.00")
    assert result.total_commission == Decimal("0.00")


# ---------------------------------------------------------------------------
# Equity P&L — Scenario 7: Buy at 150, sell at 160, qty 100
# P&L = (160 - 150) * 100 - commissions
# ---------------------------------------------------------------------------


def test_calculate_equity_pnl_profit() -> None:
    """Standard equity buy-low sell-high: positive P&L."""
    result = calculate_equity_pnl(
        cost_basis_per_share=Decimal("150.00"),
        quantity_sold=Decimal("100"),
        sell_price=Decimal("160.00"),
        open_commission=Decimal("0.65"),
        close_commission=Decimal("0.65"),
    )

    assert result.realized_pnl == Decimal("998.70")  # 1000 - 1.30
    assert result.cost_basis == Decimal("15000.00")
    assert result.sale_proceeds == Decimal("16000.00")
    assert result.total_commission == Decimal("1.30")


# ---------------------------------------------------------------------------
# Scenario 8: Assignment lot — cost_basis = strike price, sell for profit
# Strike = 50.00, qty = 100 shares, sell at 55.00
# P&L = (55 - 50) * 100 - commissions = 500 - 1.30 = 498.70
# ---------------------------------------------------------------------------


def test_calculate_equity_pnl_assignment_lot_sell_for_profit() -> None:
    """Equity lot from options assignment: cost basis is the strike price."""
    result = calculate_equity_pnl(
        cost_basis_per_share=Decimal("50.00"),
        quantity_sold=Decimal("100"),
        sell_price=Decimal("55.00"),
        open_commission=Decimal("0.65"),
        close_commission=Decimal("0.65"),
    )

    assert result.realized_pnl == Decimal("498.70")
    assert result.cost_basis == Decimal("5000.00")
    assert result.sale_proceeds == Decimal("5500.00")
    assert result.total_commission == Decimal("1.30")


# ---------------------------------------------------------------------------
# Scenario 9: Negative equity P&L (sell at loss)
# Buy at 200, sell at 180, qty 50
# P&L = (180 - 200) * 50 - 0 = -1000
# ---------------------------------------------------------------------------


def test_calculate_equity_pnl_loss() -> None:
    """Equity sell at a loss returns negative realized_pnl."""
    result = calculate_equity_pnl(
        cost_basis_per_share=Decimal("200.00"),
        quantity_sold=Decimal("50"),
        sell_price=Decimal("180.00"),
        open_commission=Decimal("0.00"),
        close_commission=Decimal("0.00"),
    )

    assert result.realized_pnl == Decimal("-1000.00")
    assert result.cost_basis == Decimal("10000.00")
    assert result.sale_proceeds == Decimal("9000.00")
    assert result.total_commission == Decimal("0.00")


# ---------------------------------------------------------------------------
# Scenario 10: Zero commission equity trade
# ---------------------------------------------------------------------------


def test_calculate_equity_pnl_zero_commission() -> None:
    """Zero-commission equity trade: P&L equals the price difference times qty."""
    result = calculate_equity_pnl(
        cost_basis_per_share=Decimal("10.00"),
        quantity_sold=Decimal("200"),
        sell_price=Decimal("15.00"),
        open_commission=Decimal("0.00"),
        close_commission=Decimal("0.00"),
    )

    assert result.realized_pnl == Decimal("1000.00")
    assert result.total_commission == Decimal("0.00")


# ---------------------------------------------------------------------------
# Aggregation — Scenario 11: Single month, single symbol
# ---------------------------------------------------------------------------


def test_aggregate_pnl_single_month_single_symbol() -> None:
    """One options result + one equity result, same symbol, same month."""
    options_results = [
        (
            "AAPL",
            date(2026, 3, 15),
            OptionsPnlResult(
                realized_pnl=Decimal("100.00"),
                open_amount=Decimal("300.00"),
                close_amount=Decimal("-200.00"),
                total_commission=Decimal("1.30"),
            ),
        )
    ]
    equity_results = [
        (
            "AAPL",
            date(2026, 3, 20),
            EquityPnlResult(
                realized_pnl=Decimal("50.00"),
                cost_basis=Decimal("15000.00"),
                sale_proceeds=Decimal("15050.00"),
                total_commission=Decimal("1.30"),
            ),
        )
    ]

    entries = aggregate_pnl(options_results, equity_results, period="month")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.period == "2026-03"
    assert entry.symbol == "AAPL"
    assert entry.options_pnl == Decimal("100.00")
    assert entry.equity_pnl == Decimal("50.00")
    assert entry.total_pnl == Decimal("150.00")


# ---------------------------------------------------------------------------
# Scenario 12: Multiple months, same symbol → separate entries
# ---------------------------------------------------------------------------


def test_aggregate_pnl_multiple_months_same_symbol() -> None:
    """Same symbol across two months produces two separate PnlSummaryEntry rows."""
    options_results = [
        (
            "TSLA",
            date(2026, 1, 10),
            OptionsPnlResult(
                realized_pnl=Decimal("200.00"),
                open_amount=Decimal("400.00"),
                close_amount=Decimal("-200.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
        (
            "TSLA",
            date(2026, 2, 5),
            OptionsPnlResult(
                realized_pnl=Decimal("-50.00"),
                open_amount=Decimal("-100.00"),
                close_amount=Decimal("50.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
    ]

    entries = aggregate_pnl(options_results, [], period="month")

    assert len(entries) == 2
    periods = {e.period for e in entries}
    assert periods == {"2026-01", "2026-02"}

    jan = next(e for e in entries if e.period == "2026-01")
    assert jan.symbol == "TSLA"
    assert jan.options_pnl == Decimal("200.00")

    feb = next(e for e in entries if e.period == "2026-02")
    assert feb.options_pnl == Decimal("-50.00")


# ---------------------------------------------------------------------------
# Scenario 13: Multiple symbols, same month → separate entries
# ---------------------------------------------------------------------------


def test_aggregate_pnl_multiple_symbols_same_month() -> None:
    """Different symbols in the same month produce separate PnlSummaryEntry rows."""
    options_results = [
        (
            "AAPL",
            date(2026, 3, 1),
            OptionsPnlResult(
                realized_pnl=Decimal("100.00"),
                open_amount=Decimal("200.00"),
                close_amount=Decimal("-100.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
        (
            "MSFT",
            date(2026, 3, 15),
            OptionsPnlResult(
                realized_pnl=Decimal("75.00"),
                open_amount=Decimal("150.00"),
                close_amount=Decimal("-75.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
    ]

    entries = aggregate_pnl(options_results, [], period="month")

    assert len(entries) == 2
    symbols = {e.symbol for e in entries}
    assert symbols == {"AAPL", "MSFT"}

    for e in entries:
        assert e.period == "2026-03"


# ---------------------------------------------------------------------------
# Scenario 14: Year aggregation mode
# ---------------------------------------------------------------------------


def test_aggregate_pnl_year_aggregation() -> None:
    """Year-mode groups all same-year same-symbol results into one entry."""
    options_results = [
        (
            "AAPL",
            date(2026, 1, 1),
            OptionsPnlResult(
                realized_pnl=Decimal("100.00"),
                open_amount=Decimal("200.00"),
                close_amount=Decimal("-100.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
        (
            "AAPL",
            date(2026, 6, 15),
            OptionsPnlResult(
                realized_pnl=Decimal("50.00"),
                open_amount=Decimal("150.00"),
                close_amount=Decimal("-100.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
        (
            "AAPL",
            date(2025, 12, 31),
            OptionsPnlResult(
                realized_pnl=Decimal("30.00"),
                open_amount=Decimal("100.00"),
                close_amount=Decimal("-70.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
    ]

    entries = aggregate_pnl(options_results, [], period="year")

    assert len(entries) == 2  # 2026 and 2025
    periods = {e.period for e in entries}
    assert periods == {"2026", "2025"}

    y2026 = next(e for e in entries if e.period == "2026")
    assert y2026.options_pnl == Decimal("150.00")  # 100 + 50

    y2025 = next(e for e in entries if e.period == "2025")
    assert y2025.options_pnl == Decimal("30.00")


# ---------------------------------------------------------------------------
# Scenario 15: Mix of options and equity P&L in same period
# ---------------------------------------------------------------------------


def test_aggregate_pnl_mixed_options_and_equity_same_period() -> None:
    """Options P&L and equity P&L for same symbol+period are summed into total_pnl."""
    options_results = [
        (
            "SPY",
            date(2026, 3, 10),
            OptionsPnlResult(
                realized_pnl=Decimal("300.00"),
                open_amount=Decimal("500.00"),
                close_amount=Decimal("-200.00"),
                total_commission=Decimal("1.30"),
            ),
        ),
    ]
    equity_results = [
        (
            "SPY",
            date(2026, 3, 25),
            EquityPnlResult(
                realized_pnl=Decimal("200.00"),
                cost_basis=Decimal("10000.00"),
                sale_proceeds=Decimal("10200.00"),
                total_commission=Decimal("1.30"),
            ),
        ),
    ]

    entries = aggregate_pnl(options_results, equity_results, period="month")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.period == "2026-03"
    assert entry.symbol == "SPY"
    assert entry.options_pnl == Decimal("300.00")
    assert entry.equity_pnl == Decimal("200.00")
    assert entry.total_pnl == Decimal("500.00")


# ---------------------------------------------------------------------------
# Scenario 16: Empty inputs → empty result
# ---------------------------------------------------------------------------


def test_aggregate_pnl_empty_inputs_returns_empty_list() -> None:
    """Calling aggregate_pnl with no results returns an empty list."""
    entries = aggregate_pnl([], [], period="month")
    assert entries == []

    entries = aggregate_pnl([], [], period="year")
    assert entries == []


# ---------------------------------------------------------------------------
# Aggregation — open positions (realized_pnl=None) are excluded
# ---------------------------------------------------------------------------


def test_aggregate_pnl_skips_open_positions() -> None:
    """Options positions that are still open (realized_pnl=None) are excluded."""
    options_results = [
        (
            "AAPL",
            date(2026, 3, 1),
            OptionsPnlResult(
                realized_pnl=None,  # still open
                open_amount=Decimal("200.00"),
                close_amount=Decimal("0.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
        (
            "AAPL",
            date(2026, 3, 15),
            OptionsPnlResult(
                realized_pnl=Decimal("50.00"),
                open_amount=Decimal("100.00"),
                close_amount=Decimal("-50.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
    ]

    entries = aggregate_pnl(options_results, [], period="month")

    assert len(entries) == 1
    assert entries[0].options_pnl == Decimal("50.00")


# ---------------------------------------------------------------------------
# Aggregation — multiple equity results, same symbol+month, are summed
# ---------------------------------------------------------------------------


def test_aggregate_pnl_multiple_equity_results_same_period_summed() -> None:
    """Multiple equity P&L results for same symbol+month accumulate correctly."""
    equity_results = [
        (
            "NVDA",
            date(2026, 4, 5),
            EquityPnlResult(
                realized_pnl=Decimal("400.00"),
                cost_basis=Decimal("5000.00"),
                sale_proceeds=Decimal("5400.00"),
                total_commission=Decimal("1.30"),
            ),
        ),
        (
            "NVDA",
            date(2026, 4, 20),
            EquityPnlResult(
                realized_pnl=Decimal("100.00"),
                cost_basis=Decimal("3000.00"),
                sale_proceeds=Decimal("3100.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
    ]

    entries = aggregate_pnl([], equity_results, period="month")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.period == "2026-04"
    assert entry.symbol == "NVDA"
    assert entry.equity_pnl == Decimal("500.00")
    assert entry.total_pnl == Decimal("500.00")


# ---------------------------------------------------------------------------
# Type-safety: verify return types are correct dataclass instances
# ---------------------------------------------------------------------------


def test_calculate_options_pnl_returns_correct_type() -> None:
    """Return value is an OptionsPnlResult dataclass instance."""
    result = calculate_options_pnl([_open_leg("100.00"), _close_leg("-50.00")])
    assert isinstance(result, OptionsPnlResult)


def test_calculate_equity_pnl_returns_correct_type() -> None:
    """Return value is an EquityPnlResult dataclass instance."""
    result = calculate_equity_pnl(
        cost_basis_per_share=Decimal("10.00"),
        quantity_sold=Decimal("10"),
        sell_price=Decimal("12.00"),
        open_commission=Decimal("0.00"),
        close_commission=Decimal("0.00"),
    )
    assert isinstance(result, EquityPnlResult)


def test_aggregate_pnl_returns_list_of_pnl_summary_entry() -> None:
    """Return value contains PnlSummaryEntry instances."""
    options_results = [
        (
            "AAPL",
            date(2026, 3, 1),
            OptionsPnlResult(
                realized_pnl=Decimal("100.00"),
                open_amount=Decimal("200.00"),
                close_amount=Decimal("-100.00"),
                total_commission=Decimal("0.65"),
            ),
        ),
    ]
    entries = aggregate_pnl(options_results, [], period="month")
    assert all(isinstance(e, PnlSummaryEntry) for e in entries)


# ---------------------------------------------------------------------------
# Edge case: invalid period argument raises ValueError
# ---------------------------------------------------------------------------


def test_aggregate_pnl_invalid_period_raises_value_error() -> None:
    """Passing an unsupported period string raises ValueError."""
    with pytest.raises(ValueError, match="period"):
        aggregate_pnl([], [], period="week")
