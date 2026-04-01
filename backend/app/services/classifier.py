"""Transaction classifier service.

Classifies a :class:`~app.services.parser.etrade.ParsedRow` produced by the
E*TRADE CSV parser into a :class:`~app.models.enums.TransactionCategory`.

This module is intentionally a pure function module: no I/O, no database
interaction, no side effects.  Input: ``ParsedRow``.  Output:
``TransactionCategory``.

Classification rules
--------------------
Most activity types map unambiguously to a category.  Two activity types
(``Sold Short`` and ``Bought To Cover``) are ambiguous in isolation — they can
represent either an options leg or an equity short-sale / cover, so the
``ParsedRow.is_option`` flag (set by the parser's options-regex match) is used
to disambiguate.

Unknown activity types that do not match any known string fall through to the
``OTHER`` category so they are stored for record-keeping rather than silently
dropped.
"""

from __future__ import annotations

from app.models.enums import TransactionCategory
from app.services.parser.etrade import ParsedRow

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

# Unambiguous: activity type string → category (no is_option check needed).
_UNAMBIGUOUS: dict[str, TransactionCategory] = {
    "Bought": TransactionCategory.EQUITY_BUY,
    "Sold": TransactionCategory.EQUITY_SELL,
    "Bought To Open": TransactionCategory.OPTIONS_BUY_TO_OPEN,
    "Sold To Close": TransactionCategory.OPTIONS_SELL_TO_CLOSE,
    "Option Expired": TransactionCategory.OPTIONS_EXPIRED,
    "Assigned": TransactionCategory.OPTIONS_ASSIGNED,
    "Exercised": TransactionCategory.OPTIONS_EXERCISED,
    "Dividend": TransactionCategory.DIVIDEND,
    "Transfer": TransactionCategory.TRANSFER,
    "Interest": TransactionCategory.INTEREST,
    "Fee": TransactionCategory.FEE,
    "Journal": TransactionCategory.JOURNAL,
}

# Ambiguous: activity type → (category_if_option, category_if_equity)
_AMBIGUOUS: dict[str, tuple[TransactionCategory, TransactionCategory]] = {
    "Sold Short": (TransactionCategory.OPTIONS_SELL_TO_OPEN, TransactionCategory.EQUITY_SELL),
    "Bought To Cover": (TransactionCategory.OPTIONS_BUY_TO_CLOSE, TransactionCategory.EQUITY_BUY),
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_transaction(row: ParsedRow) -> TransactionCategory:
    """Classify a parsed CSV row into a :class:`TransactionCategory`.

    :param row: A :class:`~app.services.parser.etrade.ParsedRow` produced by
        the E*TRADE CSV parser.
    :returns: The :class:`~app.models.enums.TransactionCategory` that best
        describes this transaction.  Returns ``TransactionCategory.OTHER`` for
        any activity type not in the known classification tables.
    """
    activity = row.activity_type.strip()

    unambiguous = _UNAMBIGUOUS.get(activity)
    if unambiguous is not None:
        return unambiguous

    ambiguous = _AMBIGUOUS.get(activity)
    if ambiguous is not None:
        option_category, equity_category = ambiguous
        return option_category if row.is_option else equity_category

    return TransactionCategory.OTHER
