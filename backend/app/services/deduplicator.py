"""Deduplication service for F-08.

Pure-function module: no I/O, no database interaction, no side effects.

Input:
  - ``new_rows``: list of :class:`~app.services.parser.etrade.ParsedRow` objects
    produced by the E*TRADE parser (F-06).
  - ``existing_transactions``: list of dicts representing already-stored
    transactions (keyed by the 10-field composite key columns).

Output:
  - list of :class:`DeduplicationResult` — one per input row, preserving order.

Deduplication tiers (D2, D16 in PRD):

  **Full 10-field composite key match** → ``DUPLICATE``
    All of trade_date, transaction_date, settlement_date, activity_type,
    description, symbol, quantity, price, amount, commission must match
    exactly.  NULL-safe: ``None == None`` is treated as a match.

  **Partial 4-field key match** → ``POSSIBLE_DUPLICATE``
    trade_date + symbol + quantity + amount all match, but at least one
    other composite-key field differs.  Surfaced for user review.

  **No match** → ``ACTIVE``

"First upload wins" semantics: existing records are never mutated.  Only the
status of the incoming (new) row is set.  Within-batch duplicates are also
detected: rows processed earlier in the same batch act as "existing" for
subsequent rows.

Complexity:
  - O(N) build phase for both lookup structures (N = existing + earlier batch rows)
  - O(1) per row for both key lookups
  - Total O(M + N) where M = len(new_rows), N = len(existing_transactions)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.enums import RawTransactionStatus
from app.services.parser.etrade import ParsedRow

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

# The composite key is a 10-tuple of (possibly None) values.
# Using a tuple allows O(1) set membership tests with correct None equality.
_CompositeKey = tuple[
    date | None,  # trade_date
    date,  # transaction_date
    date | None,  # settlement_date
    str,  # activity_type
    str,  # description
    str | None,  # symbol
    Decimal | None,  # quantity
    Decimal | None,  # price
    Decimal | None,  # amount
    Decimal,  # commission
]

# The 5-field partial key for POSSIBLE_DUPLICATE detection.
# Includes description to distinguish different option contracts on the same
# underlying (e.g. two Option Expired rows with different strikes but the
# same trade_date, symbol, quantity, and amount=0).
_PartialKey = tuple[
    date | None,  # trade_date
    str | None,  # symbol
    Decimal | None,  # quantity
    Decimal | None,  # amount
    str,  # description
]


@dataclass
class DeduplicationResult:
    """Outcome of deduplication for a single parsed row.

    Attributes:
        row: The original :class:`ParsedRow` (reference preserved).
        status: ``ACTIVE``, ``DUPLICATE``, or ``POSSIBLE_DUPLICATE``.
        matched_upload_id: UUID string of the upload that owns the matching
            existing record when status is ``DUPLICATE``; ``None`` otherwise
            (including within-batch duplicates which have no prior upload).
    """

    row: ParsedRow
    status: RawTransactionStatus
    matched_upload_id: str | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _composite_key(
    trade_date: date | None,
    transaction_date: date,
    settlement_date: date | None,
    activity_type: str,
    description: str,
    symbol: str | None,
    quantity: Decimal | None,
    price: Decimal | None,
    amount: Decimal | None,
    commission: Decimal,
) -> _CompositeKey:
    """Build the 10-field composite deduplication key tuple."""
    return (
        trade_date,
        transaction_date,
        settlement_date,
        activity_type,
        description,
        symbol,
        quantity,
        price,
        amount,
        commission,
    )


def _partial_key(
    trade_date: date | None,
    symbol: str | None,
    quantity: Decimal | None,
    amount: Decimal | None,
    description: str,
) -> _PartialKey:
    """Build the 5-field partial deduplication key tuple."""
    return (trade_date, symbol, quantity, amount, description)


def _row_composite_key(row: ParsedRow) -> _CompositeKey:
    """Extract the 10-field composite key from a :class:`ParsedRow`."""
    return _composite_key(
        trade_date=row.trade_date,
        transaction_date=row.transaction_date,
        settlement_date=row.settlement_date,
        activity_type=row.activity_type,
        description=row.description,
        symbol=row.symbol,
        quantity=row.quantity,
        price=row.price,
        amount=row.amount,
        commission=row.commission,
    )


def _row_partial_key(row: ParsedRow) -> _PartialKey:
    """Extract the 5-field partial key from a :class:`ParsedRow`."""
    return _partial_key(
        trade_date=row.trade_date,
        symbol=row.symbol,
        quantity=row.quantity,
        amount=row.amount,
        description=row.description,
    )


def _existing_composite_key(tx: dict[str, object]) -> _CompositeKey:
    """Extract the 10-field composite key from an existing-transaction dict."""
    return _composite_key(
        trade_date=tx.get("trade_date"),  # type: ignore[arg-type]
        transaction_date=tx["transaction_date"],  # type: ignore[arg-type]
        settlement_date=tx.get("settlement_date"),  # type: ignore[arg-type]
        activity_type=str(tx["activity_type"]),
        description=str(tx["description"]),
        symbol=tx.get("symbol"),  # type: ignore[arg-type]
        quantity=tx.get("quantity"),  # type: ignore[arg-type]
        price=tx.get("price"),  # type: ignore[arg-type]
        amount=tx.get("amount"),  # type: ignore[arg-type]
        commission=tx["commission"],  # type: ignore[arg-type]
    )


def _existing_partial_key(tx: dict[str, object]) -> _PartialKey:
    """Extract the 5-field partial key from an existing-transaction dict."""
    return _partial_key(
        trade_date=tx.get("trade_date"),  # type: ignore[arg-type]
        symbol=tx.get("symbol"),  # type: ignore[arg-type]
        quantity=tx.get("quantity"),  # type: ignore[arg-type]
        amount=tx.get("amount"),  # type: ignore[arg-type]
        description=str(tx.get("description", "")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deduplicate_rows(
    new_rows: list[ParsedRow],
    existing_transactions: list[dict[str, object]],
) -> list[DeduplicationResult]:
    """Check each new row against existing transactions for duplicates.

    Processes rows in order.  Within the same batch, earlier rows act as
    "existing" records for subsequent rows, enabling intra-batch dedup.

    :param new_rows: Parsed rows from the current upload batch.
    :param existing_transactions: Already-stored transactions as dicts.
        Required keys: trade_date, transaction_date, settlement_date,
        activity_type, description, symbol, quantity, price, amount,
        commission, upload_id, status.
    :returns: One :class:`DeduplicationResult` per input row, in order.
    """
    # ------------------------------------------------------------------
    # Build O(1) lookup structures from existing transactions.
    # composite_key_map: composite_key → upload_id (first upload wins).
    # partial_key_set: set of 4-field keys for POSSIBLE_DUPLICATE detection.
    # ------------------------------------------------------------------
    composite_key_map: dict[_CompositeKey, str | None] = {}
    partial_key_set: set[_PartialKey] = set()

    for tx in existing_transactions:
        ck = _existing_composite_key(tx)
        if ck not in composite_key_map:
            composite_key_map[ck] = str(tx["upload_id"]) if tx.get("upload_id") else None
        partial_key_set.add(_existing_partial_key(tx))

    # ------------------------------------------------------------------
    # Process each new row.
    # After determining a row's status, add it to the lookup structures so
    # that later rows in the same batch can detect it as a duplicate.
    # ------------------------------------------------------------------
    results: list[DeduplicationResult] = []

    for row in new_rows:
        ck = _row_composite_key(row)
        pk = _row_partial_key(row)

        if ck in composite_key_map:
            # Exact match on all 10 fields → DUPLICATE.
            # matched_upload_id comes from the map (None for within-batch matches).
            status = RawTransactionStatus.DUPLICATE
            matched_upload_id = composite_key_map[ck]
        elif pk in partial_key_set:
            # Partial match (4-field) but full key differs → POSSIBLE_DUPLICATE.
            status = RawTransactionStatus.POSSIBLE_DUPLICATE
            matched_upload_id = None
        else:
            status = RawTransactionStatus.ACTIVE
            matched_upload_id = None

        results.append(
            DeduplicationResult(row=row, status=status, matched_upload_id=matched_upload_id)
        )

        # Register this row in lookup structures for within-batch dedup.
        # Use None as upload_id for within-batch entries (no prior upload owns them).
        if ck not in composite_key_map:
            composite_key_map[ck] = None
        partial_key_set.add(pk)

    return results
