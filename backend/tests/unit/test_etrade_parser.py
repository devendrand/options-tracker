"""Unit tests for the E*TRADE CSV parser.

Tests are written BEFORE the implementation (TDD: Red phase).

Coverage strategy:
- Basic parsing of a well-formed CSV with preamble rows 1-6 skipped
- Sentinel '--' handling for every nullable field
- Date parsing: MM/DD/YY -> datetime.date (20YY convention)
- Commission defaults to Decimal('0.00') when blank or '--'
- Quantity stored as absolute value (negative in CSV becomes positive)
- Options description regex extraction for CALL and PUT
- Non-option descriptions (equity, dividend, transfer, interest, fee, journal)
- Option Expired — price defaults to Decimal('0.00'), not a parse error
- Trailing blank rows and disclaimer rows are skipped
- Empty CSV (only preamble) returns empty list
- DRIP dividend rows pass through normally as standard Dividend rows (OQ4)
- All activity type variants preserved faithfully (OQ5):
    Bought To Open, Sold To Close, Sold Short, Bought To Cover
- Fractional equity quantity (Decimal)
- raw_data dict contains the original CSV row
"""

from __future__ import annotations

from decimal import Decimal

from app.services.parser.etrade import ParsedRow, parse_etrade_csv

# ---------------------------------------------------------------------------
# CSV fixture helpers
# ---------------------------------------------------------------------------

_PREAMBLE = """\
Brokerage,E*TRADE Securities LLC
Account Number,xxxx-1234
Account Name,Individual Brokerage Account
Report Date,03/31/26
Date Range,All
,
"""

_HEADER = (
    "Transaction Date,Activity Type,Description,Symbol,"
    "Quantity,Price $,Amount $,Commission,Settlement Date\n"
)


def _make_csv(*data_rows: str) -> str:
    """Build a valid E*TRADE CSV string with preamble + header + data rows."""
    # Preamble is rows 1-6 (6 lines), header is row 7, data follows
    return _PREAMBLE + _HEADER + "".join(data_rows)


def _row(
    transaction_date: str = "03/15/26",
    activity_type: str = "Bought",
    description: str = "NVDA",
    symbol: str = "NVDA",
    quantity: str = "10",
    price: str = "105.00",
    amount: str = "-1050.00",
    commission: str = "",
    settlement_date: str = "03/17/26",
) -> str:
    """Return a single CSV data row string."""
    return (
        f"{transaction_date},{activity_type},{description},{symbol},"
        f"{quantity},{price},{amount},{commission},{settlement_date}\n"
    )


# ---------------------------------------------------------------------------
# Test: basic parsing
# ---------------------------------------------------------------------------


class TestBasicParsing:
    def test_parse_single_equity_buy_row_returns_one_result(self) -> None:
        csv_content = _make_csv(_row())
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1

    def test_parse_returns_list_of_parsed_row(self) -> None:
        csv_content = _make_csv(_row())
        rows = parse_etrade_csv(csv_content)
        assert isinstance(rows[0], ParsedRow)

    def test_transaction_date_parsed_correctly(self) -> None:
        from datetime import date

        csv_content = _make_csv(_row(transaction_date="03/15/26"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].transaction_date == date(2026, 3, 15)

    def test_activity_type_preserved_faithfully(self) -> None:
        csv_content = _make_csv(_row(activity_type="Bought"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Bought"

    def test_description_preserved_faithfully(self) -> None:
        csv_content = _make_csv(_row(description="NVIDIA CORP COM"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].description == "NVIDIA CORP COM"

    def test_symbol_parsed_correctly(self) -> None:
        csv_content = _make_csv(_row(symbol="NVDA"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].symbol == "NVDA"

    def test_quantity_positive_for_buy(self) -> None:
        csv_content = _make_csv(_row(quantity="10"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity == Decimal("10")

    def test_price_parsed_as_decimal(self) -> None:
        csv_content = _make_csv(_row(price="105.50"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].price == Decimal("105.50")

    def test_amount_negative_for_buy(self) -> None:
        csv_content = _make_csv(_row(amount="-1050.00"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].amount == Decimal("-1050.00")

    def test_settlement_date_parsed_correctly(self) -> None:
        from datetime import date

        csv_content = _make_csv(_row(settlement_date="03/17/26"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].settlement_date == date(2026, 3, 17)

    def test_multiple_rows_parsed_in_order(self) -> None:
        csv_content = _make_csv(
            _row(transaction_date="03/10/26", symbol="AAPL"),
            _row(transaction_date="03/11/26", symbol="NVDA"),
            _row(transaction_date="03/12/26", symbol="SPY"),
        )
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 3
        assert rows[0].symbol == "AAPL"
        assert rows[1].symbol == "NVDA"
        assert rows[2].symbol == "SPY"

    def test_raw_data_contains_original_csv_row_as_dict(self) -> None:
        csv_content = _make_csv(_row(symbol="NVDA", activity_type="Bought"))
        rows = parse_etrade_csv(csv_content)
        assert "Activity Type" in rows[0].raw_data
        assert rows[0].raw_data["Activity Type"] == "Bought"
        assert rows[0].raw_data["Symbol"] == "NVDA"

    def test_non_option_row_has_is_option_false(self) -> None:
        csv_content = _make_csv(_row(description="NVIDIA CORP COM"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is False

    def test_non_option_row_has_none_option_fields(self) -> None:
        csv_content = _make_csv(_row(description="NVIDIA CORP COM"))
        rows = parse_etrade_csv(csv_content)
        row = rows[0]
        assert row.option_type is None
        assert row.underlying is None
        assert row.strike is None
        assert row.expiry is None


# ---------------------------------------------------------------------------
# Test: preamble and trailing row handling
# ---------------------------------------------------------------------------


class TestPreambleAndTrailingRows:
    def test_empty_csv_only_preamble_returns_empty_list(self) -> None:
        csv_content = _PREAMBLE + _HEADER
        rows = parse_etrade_csv(csv_content)
        assert rows == []

    def test_trailing_blank_rows_are_skipped(self) -> None:
        csv_content = _make_csv(_row(), "\n", "\n", "\n")
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1

    def test_trailing_disclaimer_row_is_skipped(self) -> None:
        # E*TRADE appends a disclaimer footer that starts with a non-date value
        disclaimer = "The data and information in this spreadsheet are provided by E*TRADE\n"
        csv_content = _make_csv(_row(), disclaimer)
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1

    def test_preamble_rows_not_included_as_data(self) -> None:
        # If preamble were included, the first row would fail date parsing;
        # a successful parse of 1 row confirms preamble was correctly skipped.
        csv_content = _make_csv(_row())
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1
        assert rows[0].transaction_date is not None


# ---------------------------------------------------------------------------
# Test: sentinel '--' handling
# ---------------------------------------------------------------------------


class TestSentinelHandling:
    def test_symbol_sentinel_returns_none(self) -> None:
        csv_content = _make_csv(_row(symbol="--"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].symbol is None

    def test_quantity_sentinel_returns_none(self) -> None:
        csv_content = _make_csv(_row(quantity="--"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity is None

    def test_price_sentinel_returns_none(self) -> None:
        csv_content = _make_csv(_row(price="--"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].price is None

    def test_amount_sentinel_returns_none(self) -> None:
        csv_content = _make_csv(_row(amount="--"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].amount is None

    def test_commission_sentinel_returns_zero(self) -> None:
        csv_content = _make_csv(_row(commission="--"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].commission == Decimal("0.00")

    def test_settlement_date_sentinel_returns_none(self) -> None:
        csv_content = _make_csv(_row(settlement_date="--"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].settlement_date is None


# ---------------------------------------------------------------------------
# Test: date parsing
# ---------------------------------------------------------------------------


class TestDateParsing:
    def test_date_two_digit_year_maps_to_2000s(self) -> None:
        from datetime import date

        csv_content = _make_csv(_row(transaction_date="01/05/26"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].transaction_date == date(2026, 1, 5)

    def test_date_year_99_maps_to_2099(self) -> None:
        from datetime import date

        csv_content = _make_csv(_row(transaction_date="12/31/99"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].transaction_date == date(2099, 12, 31)

    def test_date_year_00_maps_to_2000(self) -> None:
        from datetime import date

        csv_content = _make_csv(_row(transaction_date="01/01/00"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].transaction_date == date(2000, 1, 1)

    def test_settlement_date_two_digit_year_maps_to_2000s(self) -> None:
        from datetime import date

        csv_content = _make_csv(_row(settlement_date="06/18/26"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].settlement_date == date(2026, 6, 18)

    def test_options_expiry_date_parsed_correctly(self) -> None:
        from datetime import date

        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].expiry == date(2026, 6, 18)


# ---------------------------------------------------------------------------
# Test: commission defaults
# ---------------------------------------------------------------------------


class TestCommissionDefaults:
    def test_blank_commission_defaults_to_zero(self) -> None:
        csv_content = _make_csv(_row(commission=""))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].commission == Decimal("0.00")

    def test_commission_parsed_when_provided(self) -> None:
        csv_content = _make_csv(_row(commission="0.65"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].commission == Decimal("0.65")

    def test_commission_type_is_decimal(self) -> None:
        csv_content = _make_csv(_row(commission="0.65"))
        rows = parse_etrade_csv(csv_content)
        assert isinstance(rows[0].commission, Decimal)


# ---------------------------------------------------------------------------
# Test: quantity is absolute value
# ---------------------------------------------------------------------------


class TestQuantityAbsoluteValue:
    def test_negative_quantity_in_csv_stored_as_positive(self) -> None:
        csv_content = _make_csv(_row(quantity="-5"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity == Decimal("5")

    def test_positive_quantity_unchanged(self) -> None:
        csv_content = _make_csv(_row(quantity="3"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity == Decimal("3")

    def test_fractional_equity_quantity(self) -> None:
        """Equity quantities may be fractional Decimal (D21)."""
        csv_content = _make_csv(_row(quantity="0.12345"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity == Decimal("0.12345")

    def test_fractional_negative_quantity_stored_as_positive(self) -> None:
        csv_content = _make_csv(_row(quantity="-0.12345"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity == Decimal("0.12345")


# ---------------------------------------------------------------------------
# Test: options description regex extraction
# ---------------------------------------------------------------------------


class TestOptionsDescriptionParsing:
    def test_call_description_sets_is_option_true(self) -> None:
        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is True

    def test_put_description_sets_is_option_true(self) -> None:
        description = "PUT SPY 04/24/26 600.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="SPY")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is True

    def test_call_option_type_extracted(self) -> None:
        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].option_type == "CALL"

    def test_put_option_type_extracted(self) -> None:
        description = "PUT SPY 04/24/26 600.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="SPY")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].option_type == "PUT"

    def test_underlying_extracted_from_call_description(self) -> None:
        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].underlying == "NVDA"

    def test_underlying_extracted_from_put_description(self) -> None:
        description = "PUT SPY 04/24/26 600.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="SPY")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].underlying == "SPY"

    def test_strike_extracted_from_call_description(self) -> None:
        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].strike == Decimal("220.00")

    def test_strike_extracted_from_put_description(self) -> None:
        description = "PUT SPY 04/24/26 600.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="SPY")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].strike == Decimal("600.00")

    def test_expiry_extracted_from_call_description(self) -> None:
        from datetime import date

        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].expiry == date(2026, 6, 18)

    def test_expiry_extracted_from_put_description(self) -> None:
        from datetime import date

        description = "PUT SPY 04/24/26 600.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="SPY")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].expiry == date(2026, 4, 24)

    def test_option_with_whole_number_strike(self) -> None:
        description = "CALL AAPL 01/17/25 200"
        csv_content = _make_csv(
            _row(activity_type="Bought To Open", description=description, symbol="AAPL")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is True
        assert rows[0].strike == Decimal("200")

    def test_option_underlying_with_numbers_in_ticker(self) -> None:
        """Underlying ticker that contains no spaces — regex uses non-whitespace match."""
        description = "PUT BRK.B 12/19/25 400.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="BRK.B")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is True
        assert rows[0].underlying == "BRK.B"


# ---------------------------------------------------------------------------
# Test: non-option activity types
# ---------------------------------------------------------------------------


class TestNonOptionActivityTypes:
    def test_equity_bought_row(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Bought",
                description="APPLE INC COM",
                symbol="AAPL",
                quantity="100",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is False
        assert rows[0].activity_type == "Bought"

    def test_equity_sold_row(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Sold",
                description="APPLE INC COM",
                symbol="AAPL",
                quantity="100",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is False
        assert rows[0].activity_type == "Sold"

    def test_dividend_row(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Dividend",
                description="APPLE INC COM",
                symbol="AAPL",
                quantity="--",
                price="--",
                amount="12.50",
                settlement_date="03/20/26",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is False
        assert rows[0].activity_type == "Dividend"
        assert rows[0].quantity is None

    def test_transfer_row(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Transfer",
                description="TRNSFR FROM ACCOUNT xxxx",
                symbol="--",
                quantity="--",
                price="--",
                amount="10000.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is False
        assert rows[0].activity_type == "Transfer"

    def test_interest_row(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Interest",
                description="INTEREST EARNED",
                symbol="--",
                quantity="--",
                price="--",
                amount="5.23",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is False
        assert rows[0].activity_type == "Interest"

    def test_fee_row(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Fee",
                description="SERVICE FEE",
                symbol="--",
                quantity="--",
                price="--",
                amount="-25.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is False
        assert rows[0].activity_type == "Fee"

    def test_journal_row(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Journal",
                description="JOURNAL ENTRY",
                symbol="--",
                quantity="--",
                price="--",
                amount="0.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is False
        assert rows[0].activity_type == "Journal"


# ---------------------------------------------------------------------------
# Test: Option Expired — price defaults to 0.00
# ---------------------------------------------------------------------------


class TestOptionExpired:
    def test_option_expired_blank_price_defaults_to_zero(self) -> None:
        description = "CALL NVDA 03/21/26 180.00"
        csv_content = _make_csv(
            _row(
                activity_type="Option Expired",
                description=description,
                symbol="NVDA",
                quantity="-1",
                price="",
                amount="0.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].price == Decimal("0.00")

    def test_option_expired_is_option_true(self) -> None:
        description = "PUT SPY 03/21/26 500.00"
        csv_content = _make_csv(
            _row(
                activity_type="Option Expired",
                description=description,
                symbol="SPY",
                quantity="-1",
                price="",
                amount="0.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is True

    def test_option_expired_quantity_absolute(self) -> None:
        description = "CALL NVDA 03/21/26 180.00"
        csv_content = _make_csv(
            _row(
                activity_type="Option Expired",
                description=description,
                symbol="NVDA",
                quantity="-2",
                price="",
                amount="0.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity == Decimal("2")

    def test_option_expired_sentinel_price_defaults_to_zero(self) -> None:
        """Price '--' for Option Expired also defaults to 0.00."""
        description = "CALL NVDA 03/21/26 180.00"
        csv_content = _make_csv(
            _row(
                activity_type="Option Expired",
                description=description,
                symbol="NVDA",
                quantity="-1",
                price="--",
                amount="0.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].price == Decimal("0.00")


# ---------------------------------------------------------------------------
# Test: DRIP dividend rows (OQ4 — no special handling needed)
# ---------------------------------------------------------------------------


class TestDripDividend:
    def test_drip_credit_row_passes_through_as_dividend(self) -> None:
        """Positive-amount DRIP credit is a standard Dividend row."""
        csv_content = _make_csv(
            _row(
                activity_type="Dividend",
                description="DRIP DIVIDEND APPLE INC COM",
                symbol="AAPL",
                quantity="--",
                price="--",
                amount="15.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1
        assert rows[0].activity_type == "Dividend"
        assert rows[0].amount == Decimal("15.00")
        assert rows[0].is_option is False

    def test_drip_debit_row_passes_through_as_dividend(self) -> None:
        """Negative-amount DRIP reinvestment debit is also a standard Dividend row."""
        csv_content = _make_csv(
            _row(
                activity_type="Dividend",
                description="DRIP REINVESTMENT APPLE INC COM",
                symbol="AAPL",
                quantity="--",
                price="--",
                amount="-15.00",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1
        assert rows[0].activity_type == "Dividend"
        assert rows[0].amount == Decimal("-15.00")
        assert rows[0].is_option is False

    def test_drip_pair_both_rows_present(self) -> None:
        """Both DRIP rows in a pair are returned separately (no pairing logic)."""
        csv_content = _make_csv(
            _row(
                activity_type="Dividend",
                description="DRIP DIVIDEND APPLE INC COM",
                symbol="AAPL",
                quantity="--",
                price="--",
                amount="15.00",
            ),
            _row(
                activity_type="Dividend",
                description="DRIP REINVESTMENT APPLE INC COM",
                symbol="AAPL",
                quantity="--",
                price="--",
                amount="-15.00",
            ),
        )
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# Test: OQ5 — all activity type variants preserved faithfully
# ---------------------------------------------------------------------------


class TestActivityTypeVariants:
    """OQ5: Both E*TRADE activity type label sets must be supported."""

    # -- Unambiguous options variants (no description regex needed) --

    def test_bought_to_open_activity_type_preserved(self) -> None:
        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Bought To Open", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Bought To Open"
        assert rows[0].is_option is True

    def test_sold_to_close_activity_type_preserved(self) -> None:
        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Sold To Close", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Sold To Close"
        assert rows[0].is_option is True

    def test_bought_to_close_activity_type_preserved(self) -> None:
        description = "PUT SPY 04/24/26 600.00"
        csv_content = _make_csv(
            _row(activity_type="Bought To Close", description=description, symbol="SPY")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Bought To Close"
        assert rows[0].is_option is True

    def test_sold_to_open_activity_type_preserved(self) -> None:
        description = "PUT AAPL 01/17/25 200.00"
        csv_content = _make_csv(
            _row(activity_type="Sold To Open", description=description, symbol="AAPL")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Sold To Open"
        assert rows[0].is_option is True

    # -- Equity/standard variants (require description regex for disambiguation) --

    def test_sold_short_with_options_description(self) -> None:
        """Sold Short + options description: is_option=True, activity_type preserved."""
        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="NVDA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Sold Short"
        assert rows[0].is_option is True

    def test_sold_short_with_equity_description_1(self) -> None:
        """Sold Short + non-option description: is_option=False."""
        csv_content = _make_csv(
            _row(
                activity_type="Sold Short",
                description="NVIDIA CORP COM",
                symbol="NVDA",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Sold Short"
        assert rows[0].is_option is False

    def test_sold_short_with_equity_description_2(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Sold Short",
                description="APPLE INC COM",
                symbol="AAPL",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Sold Short"
        assert rows[0].is_option is False

    def test_sold_short_with_equity_description_3(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Sold Short",
                description="SPDR S&P 500 ETF TRUST",
                symbol="SPY",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Sold Short"
        assert rows[0].is_option is False

    def test_bought_to_cover_with_options_description(self) -> None:
        """Bought To Cover + options description: is_option=True, activity_type preserved."""
        description = "PUT SPY 04/24/26 600.00"
        csv_content = _make_csv(
            _row(activity_type="Bought To Cover", description=description, symbol="SPY")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Bought To Cover"
        assert rows[0].is_option is True

    def test_bought_to_cover_with_equity_description_1(self) -> None:
        """Bought To Cover + non-option description: is_option=False."""
        csv_content = _make_csv(
            _row(
                activity_type="Bought To Cover",
                description="NVIDIA CORP COM",
                symbol="NVDA",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Bought To Cover"
        assert rows[0].is_option is False

    def test_bought_to_cover_with_equity_description_2(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Bought To Cover",
                description="APPLE INC COM",
                symbol="AAPL",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Bought To Cover"
        assert rows[0].is_option is False

    def test_bought_to_cover_with_equity_description_3(self) -> None:
        csv_content = _make_csv(
            _row(
                activity_type="Bought To Cover",
                description="SPDR S&P 500 ETF TRUST",
                symbol="SPY",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Bought To Cover"
        assert rows[0].is_option is False

    def test_option_assigned_activity_type_preserved(self) -> None:
        description = "CALL NVDA 06/18/26 220.00"
        csv_content = _make_csv(
            _row(
                activity_type="Option Assigned",
                description=description,
                symbol="NVDA",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Option Assigned"
        assert rows[0].is_option is True

    def test_option_exercised_activity_type_preserved(self) -> None:
        description = "CALL AAPL 01/17/25 200.00"
        csv_content = _make_csv(
            _row(
                activity_type="Option Exercised",
                description=description,
                symbol="AAPL",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Option Exercised"
        assert rows[0].is_option is True


# ---------------------------------------------------------------------------
# Test: ParsedRow data model integrity
# ---------------------------------------------------------------------------


class TestParsedRowModel:
    def test_parsed_row_has_all_required_fields(self) -> None:
        csv_content = _make_csv(_row())
        row = parse_etrade_csv(csv_content)[0]
        # Verify all fields exist
        assert hasattr(row, "transaction_date")
        assert hasattr(row, "activity_type")
        assert hasattr(row, "description")
        assert hasattr(row, "symbol")
        assert hasattr(row, "quantity")
        assert hasattr(row, "price")
        assert hasattr(row, "amount")
        assert hasattr(row, "commission")
        assert hasattr(row, "settlement_date")
        assert hasattr(row, "is_option")
        assert hasattr(row, "option_type")
        assert hasattr(row, "underlying")
        assert hasattr(row, "strike")
        assert hasattr(row, "expiry")
        assert hasattr(row, "raw_data")
        assert hasattr(row, "trade_date")

    def test_trade_date_equals_transaction_date(self) -> None:
        """E*TRADE CSV has one date column; trade_date is set to transaction_date."""
        csv_content = _make_csv(_row())
        row = parse_etrade_csv(csv_content)[0]
        assert row.trade_date == row.transaction_date

    def test_commission_is_always_decimal_not_none(self) -> None:
        """Commission field type is Decimal (never None) — blank defaults to 0.00."""
        csv_content = _make_csv(_row(commission=""))
        row = parse_etrade_csv(csv_content)[0]
        assert isinstance(row.commission, Decimal)
        assert row.commission == Decimal("0.00")

    def test_raw_data_is_dict_of_str_to_str(self) -> None:
        csv_content = _make_csv(_row())
        row = parse_etrade_csv(csv_content)[0]
        assert isinstance(row.raw_data, dict)
        for k, v in row.raw_data.items():
            assert isinstance(k, str)
            assert isinstance(v, str)

    def test_raw_data_preserves_original_sentinel_value(self) -> None:
        """raw_data must store the ORIGINAL CSV value (e.g. '--'), not the parsed None."""
        csv_content = _make_csv(_row(symbol="--"))
        row = parse_etrade_csv(csv_content)[0]
        assert row.raw_data["Symbol"] == "--"
        assert row.symbol is None

    def test_is_option_is_bool(self) -> None:
        csv_content = _make_csv(_row())
        row = parse_etrade_csv(csv_content)[0]
        assert isinstance(row.is_option, bool)


# ---------------------------------------------------------------------------
# Test: edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_option_with_large_strike_price(self) -> None:
        description = "CALL TSLA 12/19/25 2000.00"
        csv_content = _make_csv(
            _row(activity_type="Bought To Open", description=description, symbol="TSLA")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].strike == Decimal("2000.00")

    def test_option_with_very_small_strike_price(self) -> None:
        description = "PUT SNDL 06/20/25 0.50"
        csv_content = _make_csv(
            _row(activity_type="Sold Short", description=description, symbol="SNDL")
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].strike == Decimal("0.50")

    def test_empty_string_returns_empty_list(self) -> None:
        """Completely empty input returns empty list without raising."""
        rows = parse_etrade_csv("")
        assert rows == []

    def test_only_header_returns_empty_list(self) -> None:
        rows = parse_etrade_csv(_HEADER)
        assert rows == []

    def test_multiple_options_rows_parsed_correctly(self) -> None:
        from datetime import date

        csv_content = _make_csv(
            _row(
                transaction_date="03/10/26",
                activity_type="Sold Short",
                description="CALL NVDA 06/18/26 220.00",
                symbol="NVDA",
                quantity="-1",
                price="2.50",
                amount="250.00",
                commission="0.65",
            ),
            _row(
                transaction_date="03/11/26",
                activity_type="Bought To Open",
                description="PUT SPY 04/24/26 600.00",
                symbol="SPY",
                quantity="2",
                price="3.00",
                amount="-600.00",
                commission="1.30",
            ),
        )
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 2

        # First row: CALL NVDA
        assert rows[0].is_option is True
        assert rows[0].option_type == "CALL"
        assert rows[0].underlying == "NVDA"
        assert rows[0].expiry == date(2026, 6, 18)
        assert rows[0].strike == Decimal("220.00")
        assert rows[0].quantity == Decimal("1")  # absolute value
        assert rows[0].commission == Decimal("0.65")

        # Second row: PUT SPY
        assert rows[1].is_option is True
        assert rows[1].option_type == "PUT"
        assert rows[1].underlying == "SPY"
        assert rows[1].expiry == date(2026, 4, 24)
        assert rows[1].strike == Decimal("600.00")
        assert rows[1].quantity == Decimal("2")
        assert rows[1].commission == Decimal("1.30")


# ---------------------------------------------------------------------------
# Test: real 13-column E*TRADE CSV format
# ---------------------------------------------------------------------------

# Real E*TRADE CSV preamble (6 lines before the header).
_REAL_PREAMBLE = (
    "All Transactions Activity Types\n"
    "\n"
    "Account Activity for Stocks -0067 from Current Year\n"
    "\n"
    "Total:,-921.88\n"
    "\n"
)

# Real E*TRADE CSV header: 13 columns including Activity/Trade Date, Cusip,
# Quantity # (not Quantity), Category, and Note.
_REAL_HEADER = (
    "Activity/Trade Date,Transaction Date,Settlement Date,Activity Type,"
    "Description,Symbol,Cusip,Quantity #,Price $,Amount $,Commission,Category,Note\n"
)


def _real_row(
    trade_date: str = "03/15/26",
    transaction_date: str = "03/15/26",
    settlement_date: str = "03/17/26",
    activity_type: str = "Bought",
    description: str = "APPLE INC COM",
    symbol: str = "AAPL",
    cusip: str = "--",
    quantity: str = "10",
    price: str = "105.00",
    amount: str = "-1050.00",
    commission: str = "0.0",
    category: str = "--",
    note: str = "--",
) -> str:
    """Return a single CSV data row in the real 13-column E*TRADE format."""
    return (
        f"{trade_date},{transaction_date},{settlement_date},{activity_type},"
        f"{description},{symbol},{cusip},{quantity},{price},{amount},"
        f"{commission},{category},{note}\n"
    )


def _make_real_csv(*data_rows: str) -> str:
    """Build a valid real-format E*TRADE CSV string."""
    return _REAL_PREAMBLE + _REAL_HEADER + "".join(data_rows)


class TestRealETradeFormat:
    """Tests using the actual 13-column E*TRADE CSV format.

    Verifies that the header normalisation (Quantity # → Quantity,
    Activity/Trade Date → Trade Date) and extra columns (Cusip, Category,
    Note) are handled correctly alongside the existing 9-column fixture format.
    """

    def test_real_format_single_equity_buy_row_returns_one_result(self) -> None:
        csv_content = _make_real_csv(_real_row())
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1

    def test_real_format_symbol_parsed_correctly(self) -> None:
        csv_content = _make_real_csv(_real_row(symbol="AAPL"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].symbol == "AAPL"

    def test_real_format_activity_type_preserved(self) -> None:
        csv_content = _make_real_csv(_real_row(activity_type="Bought"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Bought"

    def test_real_format_quantity_hash_header_normalized(self) -> None:
        """Quantity # column header is normalised to Quantity before parsing."""
        csv_content = _make_real_csv(_real_row(quantity="5"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity == Decimal("5")

    def test_real_format_negative_quantity_stored_as_positive(self) -> None:
        csv_content = _make_real_csv(_real_row(quantity="-6"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity == Decimal("6")

    def test_real_format_extra_columns_do_not_affect_result(self) -> None:
        """Cusip, Category, Note columns are present but do not affect output."""
        csv_content = _make_real_csv(_real_row(cusip="123456789", category="Equity", note="auto"))
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1
        assert rows[0].symbol == "AAPL"

    def test_real_format_options_sold_short_multi_space_description(self) -> None:
        """Multi-space options description from real E*TRADE CSV is parsed correctly."""
        csv_content = _make_real_csv(
            _real_row(
                activity_type="Sold Short",
                description="CALL NVDA   06/18/26   220.000",
                symbol="NVDA",
                quantity="-6.0",
                price="2.03",
                amount="1214.9",
                commission="3.08",
                settlement_date="03/24/26",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is True
        assert rows[0].option_type == "CALL"
        assert rows[0].underlying == "NVDA"
        assert rows[0].strike == Decimal("220.000")
        assert rows[0].quantity == Decimal("6.0")
        assert rows[0].commission == Decimal("3.08")

    def test_real_format_put_options_multi_space_description(self) -> None:
        """PUT with multi-space description (e.g. SPY put from real CSV)."""
        csv_content = _make_real_csv(
            _real_row(
                activity_type="Sold Short",
                description="PUT  SPY    04/24/26   600.000",
                symbol="SPY",
                quantity="-1.0",
                price="4.03",
                amount="402.49",
                commission="0.51",
                settlement_date="03/20/26",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is True
        assert rows[0].option_type == "PUT"
        assert rows[0].underlying == "SPY"
        assert rows[0].strike == Decimal("600.000")

    def test_real_format_dividend_blank_quantity_returns_none(self) -> None:
        """Real CSV dividend rows have empty Quantity field (,,) → None."""
        csv_content = _make_real_csv(
            _real_row(
                activity_type="Dividend",
                description="VANGUARD 500 INDX ADMIRAL",
                symbol="--",
                cusip="--",
                quantity="",
                price="",
                amount="64.39",
                commission="0.0",
                settlement_date="",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].quantity is None
        assert rows[0].price is None
        assert rows[0].amount == Decimal("64.39")
        assert rows[0].symbol is None
        assert rows[0].settlement_date is None

    def test_real_format_online_transfer_blank_numeric_fields(self) -> None:
        """Online Transfer rows have blank Quantity, Price, and no settlement date."""
        csv_content = _make_real_csv(
            _real_row(
                activity_type="Online Transfer",
                description="TRANSFER FROM XXXXXX1327 REFID:16759318395",
                symbol="--",
                cusip="--",
                quantity="",
                price="",
                amount="1000.0",
                commission="0.0",
                settlement_date="",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].activity_type == "Online Transfer"
        assert rows[0].symbol is None
        assert rows[0].quantity is None
        assert rows[0].price is None
        assert rows[0].amount == Decimal("1000.0")
        assert rows[0].settlement_date is None

    def test_real_format_transaction_date_parsed_correctly(self) -> None:
        from datetime import date

        csv_content = _make_real_csv(_real_row(transaction_date="03/23/26"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].transaction_date == date(2026, 3, 23)

    def test_real_format_trade_date_equals_transaction_date(self) -> None:
        """trade_date mirrors transaction_date in the current E*TRADE adapter."""
        from datetime import date

        csv_content = _make_real_csv(_real_row(trade_date="03/23/26", transaction_date="03/23/26"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].trade_date == date(2026, 3, 23)
        assert rows[0].trade_date == rows[0].transaction_date

    def test_real_format_settlement_date_parsed(self) -> None:
        from datetime import date

        csv_content = _make_real_csv(_real_row(settlement_date="03/24/26"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].settlement_date == date(2026, 3, 24)

    def test_real_format_trailing_disclaimer_skipped(self) -> None:
        """Footer row with fewer columns than header is filtered by _is_data_row."""
        disclaimer = "The data and information in this spreadsheet are provided by E*TRADE\n"
        csv_content = _make_real_csv(_real_row(), disclaimer)
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 1

    def test_real_format_multiple_rows_parsed_in_order(self) -> None:
        csv_content = _make_real_csv(
            _real_row(transaction_date="03/10/26", symbol="AAPL"),
            _real_row(transaction_date="03/11/26", symbol="NVDA"),
        )
        rows = parse_etrade_csv(csv_content)
        assert len(rows) == 2
        assert rows[0].symbol == "AAPL"
        assert rows[1].symbol == "NVDA"

    def test_real_format_bought_to_cover_options(self) -> None:
        """Bought To Cover with options description in real 13-column format."""
        csv_content = _make_real_csv(
            _real_row(
                activity_type="Bought To Cover",
                description="CALL SLV    03/20/26    75.000",
                symbol="SLV",
                quantity="1.0",
                price="0.13",
                amount="-13.51",
                commission="0.51",
                settlement_date="03/19/26",
            )
        )
        rows = parse_etrade_csv(csv_content)
        assert rows[0].is_option is True
        assert rows[0].option_type == "CALL"
        assert rows[0].underlying == "SLV"
        assert rows[0].commission == Decimal("0.51")

    def test_real_format_commission_zero_string(self) -> None:
        """Real CSV uses '0.0' for zero commission (not blank)."""
        csv_content = _make_real_csv(_real_row(commission="0.0"))
        rows = parse_etrade_csv(csv_content)
        assert rows[0].commission == Decimal("0.0")

    def test_real_format_raw_data_contains_original_columns(self) -> None:
        """raw_data preserves all 13 original columns including Cusip/Category/Note."""
        csv_content = _make_real_csv(_real_row())
        rows = parse_etrade_csv(csv_content)
        # Header was normalised; raw_data keys reflect the normalised header.
        assert "Transaction Date" in rows[0].raw_data
        assert "Quantity" in rows[0].raw_data
        assert "Trade Date" in rows[0].raw_data
        assert "Cusip" in rows[0].raw_data
