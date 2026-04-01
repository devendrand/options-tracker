"""Unit tests for the transaction classifier service.

Tests are written BEFORE the implementation (TDD: Red phase).

Coverage strategy:
- Every unambiguous activity type maps to the correct TransactionCategory
- Ambiguous activity types (Sold Short, Bought To Cover) dispatch on is_option
- Unknown / unrecognised activity types fall back to OTHER
- DRIP dividend rows (OQ4) — both debit and credit legs → DIVIDEND
- OQ5 paths: Bought To Open and Sold To Close
- Whitespace in activity type is stripped before matching
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import TransactionCategory
from app.services.classifier import classify_transaction
from app.services.parser.etrade import ParsedRow

# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------


def _make_row(
    activity_type: str,
    *,
    is_option: bool = False,
    description: str = "TEST ROW",
    symbol: str | None = "AAPL",
) -> ParsedRow:
    """Return a minimal ParsedRow with only the fields the classifier uses."""
    return ParsedRow(
        transaction_date=date(2024, 1, 15),
        activity_type=activity_type,
        description=description,
        symbol=symbol,
        quantity=Decimal("1"),
        price=Decimal("1.00"),
        amount=Decimal("-100.00"),
        commission=Decimal("0.00"),
        settlement_date=date(2024, 1, 17),
        is_option=is_option,
        option_type="CALL" if is_option else None,
        underlying="AAPL" if is_option else None,
        strike=Decimal("150") if is_option else None,
        expiry=date(2024, 3, 15) if is_option else None,
        raw_data={},
    )


# ---------------------------------------------------------------------------
# Unambiguous activity types — equity / misc
# ---------------------------------------------------------------------------


def test_classify_transaction_bought_returns_equity_buy() -> None:
    row = _make_row("Bought")
    assert classify_transaction(row) == TransactionCategory.EQUITY_BUY


def test_classify_transaction_sold_returns_equity_sell() -> None:
    row = _make_row("Sold")
    assert classify_transaction(row) == TransactionCategory.EQUITY_SELL


def test_classify_transaction_dividend_returns_dividend() -> None:
    row = _make_row("Dividend")
    assert classify_transaction(row) == TransactionCategory.DIVIDEND


def test_classify_transaction_transfer_returns_transfer() -> None:
    row = _make_row("Transfer")
    assert classify_transaction(row) == TransactionCategory.TRANSFER


def test_classify_transaction_interest_returns_interest() -> None:
    row = _make_row("Interest")
    assert classify_transaction(row) == TransactionCategory.INTEREST


def test_classify_transaction_fee_returns_fee() -> None:
    row = _make_row("Fee")
    assert classify_transaction(row) == TransactionCategory.FEE


def test_classify_transaction_journal_returns_journal() -> None:
    row = _make_row("Journal")
    assert classify_transaction(row) == TransactionCategory.JOURNAL


# ---------------------------------------------------------------------------
# Unambiguous activity types — options-only
# ---------------------------------------------------------------------------


def test_classify_transaction_bought_to_open_returns_options_buy_to_open() -> None:
    row = _make_row("Bought To Open", is_option=True)
    assert classify_transaction(row) == TransactionCategory.OPTIONS_BUY_TO_OPEN


def test_classify_transaction_sold_to_close_returns_options_sell_to_close() -> None:
    row = _make_row("Sold To Close", is_option=True)
    assert classify_transaction(row) == TransactionCategory.OPTIONS_SELL_TO_CLOSE


def test_classify_transaction_option_expired_returns_options_expired() -> None:
    row = _make_row("Option Expired", is_option=True)
    assert classify_transaction(row) == TransactionCategory.OPTIONS_EXPIRED


def test_classify_transaction_assigned_returns_options_assigned() -> None:
    row = _make_row("Assigned", is_option=True)
    assert classify_transaction(row) == TransactionCategory.OPTIONS_ASSIGNED


def test_classify_transaction_exercised_returns_options_exercised() -> None:
    row = _make_row("Exercised", is_option=True)
    assert classify_transaction(row) == TransactionCategory.OPTIONS_EXERCISED


# ---------------------------------------------------------------------------
# Ambiguous: Sold Short
# ---------------------------------------------------------------------------


def test_classify_transaction_sold_short_with_option_returns_sell_to_open() -> None:
    row = _make_row("Sold Short", is_option=True)
    assert classify_transaction(row) == TransactionCategory.OPTIONS_SELL_TO_OPEN


def test_classify_transaction_sold_short_without_option_returns_equity_sell() -> None:
    row = _make_row("Sold Short", is_option=False)
    assert classify_transaction(row) == TransactionCategory.EQUITY_SELL


# ---------------------------------------------------------------------------
# Ambiguous: Bought To Cover
# ---------------------------------------------------------------------------


def test_classify_transaction_bought_to_cover_with_option_returns_buy_to_close() -> None:
    row = _make_row("Bought To Cover", is_option=True)
    assert classify_transaction(row) == TransactionCategory.OPTIONS_BUY_TO_CLOSE


def test_classify_transaction_bought_to_cover_without_option_returns_equity_buy() -> None:
    row = _make_row("Bought To Cover", is_option=False)
    assert classify_transaction(row) == TransactionCategory.EQUITY_BUY


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


def test_classify_transaction_unknown_activity_type_returns_other() -> None:
    row = _make_row("Reinvestment")
    assert classify_transaction(row) == TransactionCategory.OTHER


def test_classify_transaction_empty_activity_type_returns_other() -> None:
    row = _make_row("")
    assert classify_transaction(row) == TransactionCategory.OTHER


# ---------------------------------------------------------------------------
# DRIP dividend rows (OQ4) — both debit and credit legs → DIVIDEND
# ---------------------------------------------------------------------------


def test_classify_transaction_drip_dividend_credit_returns_dividend() -> None:
    """DRIP credit leg (positive amount) should be DIVIDEND."""
    row = _make_row("Dividend", description="DRIP DIVIDEND CREDIT AAPL")
    assert classify_transaction(row) == TransactionCategory.DIVIDEND


def test_classify_transaction_drip_dividend_debit_returns_dividend() -> None:
    """DRIP debit leg (paired negative amount) should also be DIVIDEND."""
    row = _make_row("Dividend", description="DRIP DIVIDEND DEBIT AAPL")
    assert classify_transaction(row) == TransactionCategory.DIVIDEND


# ---------------------------------------------------------------------------
# OQ5: Bought To Open and Sold To Close (verify both paths covered)
# ---------------------------------------------------------------------------


def test_classify_transaction_bought_to_open_is_not_equity_buy() -> None:
    """Bought To Open must not resolve to EQUITY_BUY — this was a historic OQ5 ambiguity."""
    row = _make_row("Bought To Open", is_option=True)
    result = classify_transaction(row)
    assert result != TransactionCategory.EQUITY_BUY
    assert result == TransactionCategory.OPTIONS_BUY_TO_OPEN


def test_classify_transaction_sold_to_close_is_not_equity_sell() -> None:
    """Sold To Close must not resolve to EQUITY_SELL."""
    row = _make_row("Sold To Close", is_option=True)
    result = classify_transaction(row)
    assert result != TransactionCategory.EQUITY_SELL
    assert result == TransactionCategory.OPTIONS_SELL_TO_CLOSE


# ---------------------------------------------------------------------------
# Whitespace stripping
# ---------------------------------------------------------------------------


def test_classify_transaction_strips_leading_trailing_whitespace() -> None:
    row = _make_row("  Bought  ")
    assert classify_transaction(row) == TransactionCategory.EQUITY_BUY


def test_classify_transaction_strips_whitespace_on_ambiguous_type() -> None:
    row = _make_row("  Sold Short  ", is_option=True)
    assert classify_transaction(row) == TransactionCategory.OPTIONS_SELL_TO_OPEN


@pytest.mark.parametrize(
    ("activity_type", "is_option", "expected"),
    [
        ("Bought", False, TransactionCategory.EQUITY_BUY),
        ("Sold", False, TransactionCategory.EQUITY_SELL),
        ("Bought To Open", True, TransactionCategory.OPTIONS_BUY_TO_OPEN),
        ("Sold To Close", True, TransactionCategory.OPTIONS_SELL_TO_CLOSE),
        ("Option Expired", True, TransactionCategory.OPTIONS_EXPIRED),
        ("Assigned", True, TransactionCategory.OPTIONS_ASSIGNED),
        ("Exercised", True, TransactionCategory.OPTIONS_EXERCISED),
        ("Dividend", False, TransactionCategory.DIVIDEND),
        ("Transfer", False, TransactionCategory.TRANSFER),
        ("Interest", False, TransactionCategory.INTEREST),
        ("Fee", False, TransactionCategory.FEE),
        ("Journal", False, TransactionCategory.JOURNAL),
        ("Sold Short", True, TransactionCategory.OPTIONS_SELL_TO_OPEN),
        ("Sold Short", False, TransactionCategory.EQUITY_SELL),
        ("Bought To Cover", True, TransactionCategory.OPTIONS_BUY_TO_CLOSE),
        ("Bought To Cover", False, TransactionCategory.EQUITY_BUY),
        ("Unknown Activity XYZ", False, TransactionCategory.OTHER),
    ],
)
def test_classify_transaction_parametrized_full_matrix(
    activity_type: str,
    is_option: bool,
    expected: TransactionCategory,
) -> None:
    """Exhaustive parametrized sweep across all classification paths."""
    row = _make_row(activity_type, is_option=is_option)
    assert classify_transaction(row) == expected
