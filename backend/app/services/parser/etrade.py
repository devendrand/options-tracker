"""E*TRADE CSV export parser.

Parses the raw CSV content produced by E*TRADE's brokerage account
transaction history export into a list of :class:`ParsedRow` instances.

This module is a pure function module: no I/O, no database interaction,
no side effects.  Input: raw CSV string.  Output: list of ParsedRow.

E*TRADE CSV format quirks handled here:
- Rows 1–6 are a preamble (account header); row 7 is the column header.
- Trailing blank rows and disclaimer text rows are skipped.
- ``--`` sentinel means null for every field.
- Commission is blank (or ``--``) when zero; default to ``Decimal('0.00')``.
- Quantity is stored as the **absolute value**; direction is encoded by the
  classifier in F-07 from the activity type.
- ``Option Expired`` rows have a blank ``Price $`` field; default to
  ``Decimal('0.00')`` (not a parse error).
- The options description regex ``^(CALL|PUT)\\s+(\\S+)\\s+(\\d{2}/\\d{2}/\\d{2})\\s+([\\d.]+)``
  is used to detect options and extract ``option_type``, ``underlying``,
  ``expiry``, and ``strike`` from the ``Description`` field.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Number of preamble lines before the CSV header row.
_PREAMBLE_LINE_COUNT = 6

# Options description detection regex (from CLAUDE.md domain rules).
_OPTIONS_RE: re.Pattern[str] = re.compile(
    r"^(CALL|PUT)\s+(\S+)\s+(\d{2}/\d{2}/\d{2})\s+([\d.]+)",
    re.IGNORECASE,
)

# Sentinel value used by E*TRADE for null / not-applicable fields.
_SENTINEL = "--"

# Expected column names in the E*TRADE CSV header (row 7).
_COL_TRANSACTION_DATE = "Transaction Date"
_COL_ACTIVITY_TYPE = "Activity Type"
_COL_DESCRIPTION = "Description"
_COL_SYMBOL = "Symbol"
_COL_QUANTITY = "Quantity"
_COL_PRICE = "Price $"
_COL_AMOUNT = "Amount $"
_COL_COMMISSION = "Commission"
_COL_SETTLEMENT_DATE = "Settlement Date"


# ---------------------------------------------------------------------------
# Output data model
# ---------------------------------------------------------------------------


@dataclass
class ParsedRow:
    """Represents a single parsed row from an E*TRADE CSV export.

    All fields map directly to E*TRADE CSV columns, with the following
    normalizations applied:
    - ``--`` sentinel → ``None`` (except ``commission`` → ``Decimal('0.00')``)
    - Dates converted from ``MM/DD/YY`` to :class:`datetime.date` (20YY)
    - ``quantity`` stored as absolute value (``Decimal``)
    - Options metadata extracted from ``description`` via regex
    - ``raw_data`` preserves the original CSV row dict verbatim for storage
      in ``RawTransaction.raw_data``

    ``trade_date`` is set equal to ``transaction_date`` for E*TRADE exports
    (E*TRADE's CSV only exposes one date field).  It is kept as a separate
    field to match the 10-field composite deduplication key (F-08) and to
    allow future broker adapters to supply distinct trade vs settlement dates.
    """

    transaction_date: date
    activity_type: str
    description: str
    symbol: str | None
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal | None
    commission: Decimal
    settlement_date: date | None
    is_option: bool
    option_type: str | None
    underlying: str | None
    strike: Decimal | None
    expiry: date | None
    raw_data: dict[str, str]
    # trade_date mirrors transaction_date for E*TRADE; kept separate for the
    # composite dedup key and future broker adapters.
    trade_date: date | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> date:
    """Parse a ``MM/DD/YY`` string into a :class:`datetime.date`.

    The 2-digit year is always interpreted as 20YY (per domain rules).
    """
    month, day, year_2 = value.strip().split("/")
    return date(2000 + int(year_2), int(month), int(day))


def _parse_optional_date(value: str) -> date | None:
    """Return ``None`` for sentinel/blank; otherwise parse the date."""
    stripped = value.strip()
    if not stripped or stripped == _SENTINEL:
        return None
    return _parse_date(stripped)


def _parse_optional_decimal(value: str) -> Decimal | None:
    """Return ``None`` for sentinel/blank; otherwise return a ``Decimal``."""
    stripped = value.strip()
    if not stripped or stripped == _SENTINEL:
        return None
    return Decimal(stripped)


def _parse_commission(value: str) -> Decimal:
    """Return ``Decimal('0.00')`` for blank or sentinel; otherwise parse."""
    stripped = value.strip()
    if not stripped or stripped == _SENTINEL:
        return Decimal("0.00")
    return Decimal(stripped)


def _parse_optional_symbol(value: str) -> str | None:
    """Return ``None`` for sentinel/blank; otherwise return the raw string."""
    stripped = value.strip()
    if not stripped or stripped == _SENTINEL:
        return None
    return stripped


def _parse_price(value: str, activity_type: str) -> Decimal | None:
    """Parse the ``Price $`` field.

    Special case: ``Option Expired`` rows have a blank (or ``--``) price
    field; this is not an error — default to ``Decimal('0.00')``.
    """
    stripped = value.strip()
    if not stripped or stripped == _SENTINEL:
        if activity_type.strip() == "Option Expired":
            return Decimal("0.00")
        return None
    return Decimal(stripped)


def _extract_options_metadata(
    description: str,
) -> tuple[bool, str | None, str | None, Decimal | None, date | None]:
    """Try to match the options description regex against ``description``.

    Returns a 5-tuple:
      (is_option, option_type, underlying, strike, expiry)

    If the regex does not match, all extracted fields are ``None`` and
    ``is_option`` is ``False``.
    """
    match = _OPTIONS_RE.match(description.strip())
    if match is None:
        return False, None, None, None, None

    raw_opt_type, underlying, expiry_str, strike_str = match.groups()
    option_type = raw_opt_type.upper()
    expiry = _parse_date(expiry_str)
    strike = Decimal(strike_str)
    return True, option_type, underlying, strike, expiry


def _is_data_row(row: dict[str, str]) -> bool:
    """Return ``True`` if ``row`` is a parseable data row.

    Skips non-data footer/disclaimer rows by checking whether the
    ``Transaction Date`` field matches the expected ``MM/DD/YY`` pattern.
    ``csv.DictReader`` already omits completely blank lines, so we only
    need to guard against disclaimer text in the first column.
    """
    raw_date = row.get(_COL_TRANSACTION_DATE, "").strip()
    # A valid date field matches MM/DD/YY; anything else (empty or text) is skipped.
    return bool(re.match(r"^\d{2}/\d{2}/\d{2}$", raw_date))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_etrade_csv(content: str) -> list[ParsedRow]:
    """Parse E*TRADE CSV export content and return a list of parsed rows.

    :param content: The full text of an E*TRADE CSV transaction export.
    :returns: A list of :class:`ParsedRow` instances — one per valid data
              row in the CSV, in order of appearance.  Returns an empty
              list if no data rows are present.

    The function:
    1. Strips the 6-line preamble (rows 1–6).
    2. Reads row 7 as the CSV header.
    3. Parses each subsequent row, skipping blank and disclaimer rows.
    4. Normalises each field per E*TRADE domain rules (see module docstring).
    """
    if not content.strip():
        return []

    lines = content.splitlines()

    # Strip the preamble (lines 0..5) and pass the remainder to csv.DictReader.
    # If the content has fewer lines than the preamble, there are no data rows.
    if len(lines) <= _PREAMBLE_LINE_COUNT:
        return []

    data_lines = lines[_PREAMBLE_LINE_COUNT:]

    # Normalise header: map real E*TRADE column names to internal names.
    # Real CSV uses "Quantity #" and "Activity/Trade Date"; our parser
    # expects "Quantity" and "Transaction Date". Handle both formats.
    data_lines[0] = (
        data_lines[0]
        .replace("Quantity #", "Quantity")
        .replace("Activity/Trade Date", "Trade Date")
    )

    reader = csv.DictReader(io.StringIO("\n".join(data_lines)))

    results: list[ParsedRow] = []

    for row in reader:
        # Skip blank rows and footer/disclaimer text rows.
        if not _is_data_row(row):
            continue

        raw_data: dict[str, str] = dict(row)

        transaction_date = _parse_date(row[_COL_TRANSACTION_DATE])
        activity_type = row[_COL_ACTIVITY_TYPE].strip()
        description = row[_COL_DESCRIPTION].strip()

        symbol = _parse_optional_symbol(row[_COL_SYMBOL])

        raw_quantity = _parse_optional_decimal(row[_COL_QUANTITY])
        quantity = abs(raw_quantity) if raw_quantity is not None else None

        price = _parse_price(row[_COL_PRICE], activity_type)
        amount = _parse_optional_decimal(row[_COL_AMOUNT])
        commission = _parse_commission(row[_COL_COMMISSION])
        settlement_date = _parse_optional_date(row[_COL_SETTLEMENT_DATE])

        is_option, option_type, underlying, strike, expiry = _extract_options_metadata(description)

        results.append(
            ParsedRow(
                transaction_date=transaction_date,
                activity_type=activity_type,
                description=description,
                symbol=symbol,
                quantity=quantity,
                price=price,
                amount=amount,
                commission=commission,
                settlement_date=settlement_date,
                is_option=is_option,
                option_type=option_type,
                underlying=underlying,
                strike=strike,
                expiry=expiry,
                raw_data=raw_data,
                # E*TRADE exposes a single date column; trade_date = transaction_date.
                trade_date=transaction_date,
            )
        )

    return results
