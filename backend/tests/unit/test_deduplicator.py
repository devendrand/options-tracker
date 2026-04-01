"""Unit tests for the deduplication service (F-08).

Tests are written before the implementation (TDD).

Coverage strategy:
- Test deduplicate_rows() as the public API
- Cover all 3 status outcomes: ACTIVE, DUPLICATE, POSSIBLE_DUPLICATE
- Cover NULL-safe matching for every nullable field in the composite key
- Cover within-batch duplicate detection (rows in the same batch can dedup each other)
- Cover Decimal precision matching
- No DB required — purely in-memory list operations

Composite key (10 fields):
  trade_date, transaction_date, settlement_date, activity_type, description,
  symbol, quantity, price, amount, commission
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.models.enums import RawTransactionStatus
from app.services.deduplicator import DeduplicationResult, deduplicate_rows
from app.services.parser.etrade import ParsedRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    trade_date: date = date(2026, 1, 15),
    transaction_date: date = date(2026, 1, 15),
    settlement_date: date | None = date(2026, 1, 17),
    activity_type: str = "Sold Short",
    description: str = "CALL NVDA 06/18/26 220.00",
    symbol: str | None = "NVDA",
    quantity: Decimal | None = Decimal("1.00000"),
    price: Decimal | None = Decimal("2.50"),
    amount: Decimal | None = Decimal("250.00"),
    commission: Decimal = Decimal("0.65"),
) -> ParsedRow:
    """Build a ParsedRow with sensible defaults for dedup tests."""
    return ParsedRow(
        transaction_date=transaction_date,
        activity_type=activity_type,
        description=description,
        symbol=symbol,
        quantity=quantity,
        price=price,
        amount=amount,
        commission=commission,
        settlement_date=settlement_date,
        is_option=True,
        option_type="CALL",
        underlying="NVDA",
        strike=Decimal("220.00"),
        expiry=date(2026, 6, 18),
        raw_data={},
        trade_date=trade_date,
    )


def _make_existing(
    upload_id: str | None = None,
    trade_date: date = date(2026, 1, 15),
    transaction_date: date = date(2026, 1, 15),
    settlement_date: date | None = date(2026, 1, 17),
    activity_type: str = "Sold Short",
    description: str = "CALL NVDA 06/18/26 220.00",
    symbol: str | None = "NVDA",
    quantity: Decimal | None = Decimal("1.00000"),
    price: Decimal | None = Decimal("2.50"),
    amount: Decimal | None = Decimal("250.00"),
    commission: Decimal = Decimal("0.65"),
    status: str = "ACTIVE",
) -> dict[str, object]:
    """Build an existing-transaction dict as would come from the DB layer."""
    return {
        "upload_id": upload_id or str(uuid.uuid4()),
        "trade_date": trade_date,
        "transaction_date": transaction_date,
        "settlement_date": settlement_date,
        "activity_type": activity_type,
        "description": description,
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "amount": amount,
        "commission": commission,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Test: empty inputs
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    def test_empty_new_rows_returns_empty_list(self) -> None:
        """No new rows → empty result list."""
        result = deduplicate_rows([], [])
        assert result == []

    def test_empty_new_rows_with_existing_transactions(self) -> None:
        """No new rows even when existing transactions are present."""
        existing = [_make_existing()]
        result = deduplicate_rows([], existing)
        assert result == []


# ---------------------------------------------------------------------------
# Test: all ACTIVE (no existing transactions)
# ---------------------------------------------------------------------------


class TestNoExistingTransactions:
    def test_single_row_no_existing_is_active(self) -> None:
        row = _make_row()
        results = deduplicate_rows([row], [])
        assert len(results) == 1
        assert results[0].status == RawTransactionStatus.ACTIVE
        assert results[0].matched_upload_id is None

    def test_multiple_rows_no_existing_all_active(self) -> None:
        rows = [
            _make_row(description="CALL NVDA 06/18/26 220.00", symbol="NVDA"),
            _make_row(description="PUT AAPL 06/18/26 150.00", symbol="AAPL"),
            _make_row(
                activity_type="Dividend",
                description="AAPL dividend",
                symbol="AAPL",
                trade_date=date(2026, 1, 20),
            ),
        ]
        results = deduplicate_rows(rows, [])
        assert all(r.status == RawTransactionStatus.ACTIVE for r in results)
        assert all(r.matched_upload_id is None for r in results)

    def test_result_preserves_original_row_reference(self) -> None:
        row = _make_row()
        results = deduplicate_rows([row], [])
        assert results[0].row is row


# ---------------------------------------------------------------------------
# Test: DUPLICATE — exact match on all 10 fields
# ---------------------------------------------------------------------------


class TestExactMatchDuplicate:
    def test_exact_match_is_duplicate(self) -> None:
        upload_id = str(uuid.uuid4())
        existing = [_make_existing(upload_id=upload_id)]
        row = _make_row()
        results = deduplicate_rows([row], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE
        assert results[0].matched_upload_id == upload_id

    def test_duplicate_records_matched_upload_id(self) -> None:
        """The matched_upload_id is from the ACTIVE existing record."""
        owner_id = str(uuid.uuid4())
        existing = [_make_existing(upload_id=owner_id, status="ACTIVE")]
        results = deduplicate_rows([_make_row()], existing)
        assert results[0].matched_upload_id == owner_id

    def test_no_match_is_active_not_duplicate(self) -> None:
        existing = [_make_existing(symbol="AAPL")]  # different symbol
        results = deduplicate_rows([_make_row(symbol="NVDA")], existing)
        assert results[0].status == RawTransactionStatus.ACTIVE

    def test_different_activity_type_falls_to_possible_duplicate(self) -> None:
        """Different activity_type but same 4-field partial key → POSSIBLE_DUPLICATE."""
        existing = [_make_existing(activity_type="Bought To Cover")]
        results = deduplicate_rows([_make_row(activity_type="Sold Short")], existing)
        # trade_date + symbol + quantity + amount still match → POSSIBLE_DUPLICATE
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE

    def test_different_commission_falls_to_possible_duplicate(self) -> None:
        """Different commission but same 4-field partial key → POSSIBLE_DUPLICATE."""
        existing = [_make_existing(commission=Decimal("1.30"))]
        results = deduplicate_rows([_make_row(commission=Decimal("0.65"))], existing)
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE

    def test_different_description_falls_to_possible_duplicate(self) -> None:
        """Different description but same 4-field partial key → POSSIBLE_DUPLICATE."""
        existing = [_make_existing(description="PUT NVDA 06/18/26 220.00")]
        results = deduplicate_rows([_make_row(description="CALL NVDA 06/18/26 220.00")], existing)
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE

    def test_different_trade_date_is_active(self) -> None:
        """Different trade_date breaks both composite and partial keys → ACTIVE."""
        existing = [_make_existing(trade_date=date(2026, 1, 16))]
        results = deduplicate_rows([_make_row(trade_date=date(2026, 1, 15))], existing)
        assert results[0].status == RawTransactionStatus.ACTIVE

    def test_different_transaction_date_falls_to_possible_duplicate(self) -> None:
        """Different transaction_date but same 4-field partial key → POSSIBLE_DUPLICATE."""
        existing = [_make_existing(transaction_date=date(2026, 1, 16))]
        results = deduplicate_rows([_make_row(transaction_date=date(2026, 1, 15))], existing)
        # 4-field partial key (trade_date+symbol+quantity+amount) still matches
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE


# ---------------------------------------------------------------------------
# Test: POSSIBLE_DUPLICATE — partial match (4-field: trade_date+symbol+qty+amount)
# ---------------------------------------------------------------------------


class TestPartialMatchPossibleDuplicate:
    def test_partial_match_different_price_is_possible_duplicate(self) -> None:
        """Same 4-field partial key but different price → POSSIBLE_DUPLICATE."""
        existing = [_make_existing(price=Decimal("3.00"))]
        results = deduplicate_rows([_make_row(price=Decimal("2.50"))], existing)
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE
        assert results[0].matched_upload_id is None

    def test_partial_match_different_commission_is_possible_duplicate(self) -> None:
        existing = [_make_existing(commission=Decimal("1.30"))]
        # Change commission but keep all 4 partial-key fields the same
        results = deduplicate_rows([_make_row(commission=Decimal("0.65"))], existing)
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE

    def test_partial_match_different_description_is_possible_duplicate(self) -> None:
        existing = [_make_existing(description="DIFFERENT DESCRIPTION")]
        results = deduplicate_rows([_make_row()], existing)
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE

    def test_partial_match_different_activity_type_is_possible_duplicate(self) -> None:
        existing = [_make_existing(activity_type="Bought To Cover")]
        results = deduplicate_rows([_make_row(activity_type="Sold Short")], existing)
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE

    def test_no_partial_match_is_active(self) -> None:
        """If neither 10-field nor 4-field key matches, row is ACTIVE."""
        existing = [_make_existing(symbol="AAPL", amount=Decimal("500.00"))]
        results = deduplicate_rows([_make_row(symbol="NVDA", amount=Decimal("250.00"))], existing)
        assert results[0].status == RawTransactionStatus.ACTIVE


# ---------------------------------------------------------------------------
# Test: NULL handling — None == None treated as match
# ---------------------------------------------------------------------------


class TestNullSafeMatching:
    def test_null_settlement_date_matches_null(self) -> None:
        """Two rows with settlement_date=None should match on the full 10-field key."""
        existing = [_make_existing(settlement_date=None)]
        results = deduplicate_rows([_make_row(settlement_date=None)], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE

    def test_null_settlement_date_does_not_match_non_null(self) -> None:
        """settlement_date=None must not match settlement_date=<a date>."""
        existing = [_make_existing(settlement_date=date(2026, 1, 17))]
        results = deduplicate_rows([_make_row(settlement_date=None)], existing)
        # Different settlement_date → falls to partial key check → POSSIBLE_DUPLICATE
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE

    def test_null_price_matches_null_price(self) -> None:
        """Two rows with price=None should match on the full composite key."""
        existing = [_make_existing(price=None)]
        results = deduplicate_rows([_make_row(price=None)], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE

    def test_null_price_does_not_match_non_null_price(self) -> None:
        existing = [_make_existing(price=Decimal("2.50"))]
        results = deduplicate_rows([_make_row(price=None)], existing)
        # Price differs → partial key (no price) matches → POSSIBLE_DUPLICATE
        assert results[0].status == RawTransactionStatus.POSSIBLE_DUPLICATE

    def test_null_symbol_matches_null_symbol(self) -> None:
        """symbol=None on both sides should be treated as equal in composite key."""
        existing = [
            _make_existing(
                symbol=None,
                description="Interest",
                activity_type="Interest",
            )
        ]
        row = _make_row(symbol=None, description="Interest", activity_type="Interest")
        results = deduplicate_rows([row], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE

    def test_null_quantity_matches_null_quantity(self) -> None:
        existing = [_make_existing(quantity=None)]
        results = deduplicate_rows([_make_row(quantity=None)], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE

    def test_null_amount_matches_null_amount(self) -> None:
        existing = [_make_existing(amount=None)]
        results = deduplicate_rows([_make_row(amount=None)], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE


# ---------------------------------------------------------------------------
# Test: within-batch duplicate detection
# ---------------------------------------------------------------------------


class TestWithinBatchDeduplication:
    def test_second_identical_row_in_batch_is_duplicate(self) -> None:
        """Within the same batch, row 2 that is identical to row 1 → DUPLICATE."""
        row1 = _make_row()
        row2 = _make_row()  # identical fields
        results = deduplicate_rows([row1, row2], [])
        assert results[0].status == RawTransactionStatus.ACTIVE
        assert results[1].status == RawTransactionStatus.DUPLICATE

    def test_within_batch_duplicate_references_correct_batch_position(self) -> None:
        """matched_upload_id is None for within-batch duplicates (no prior upload)."""
        row1 = _make_row()
        row2 = _make_row()
        results = deduplicate_rows([row1, row2], [])
        # Within-batch match has no external upload_id; matched_upload_id is None
        assert results[1].matched_upload_id is None

    def test_third_row_duplicate_of_first_in_batch(self) -> None:
        row1 = _make_row(description="ROW1", symbol="NVDA")
        row2 = _make_row(description="ROW2", symbol="AAPL")
        row3 = _make_row(description="ROW1", symbol="NVDA")  # dup of row1
        results = deduplicate_rows([row1, row2, row3], [])
        assert results[0].status == RawTransactionStatus.ACTIVE
        assert results[1].status == RawTransactionStatus.ACTIVE
        assert results[2].status == RawTransactionStatus.DUPLICATE

    def test_within_batch_partial_match_is_possible_duplicate(self) -> None:
        """Within-batch partial match (4-field) → POSSIBLE_DUPLICATE."""
        row1 = _make_row(commission=Decimal("0.65"))
        row2 = _make_row(commission=Decimal("1.30"))  # same 4-field, different commission
        results = deduplicate_rows([row1, row2], [])
        assert results[0].status == RawTransactionStatus.ACTIVE
        assert results[1].status == RawTransactionStatus.POSSIBLE_DUPLICATE


# ---------------------------------------------------------------------------
# Test: mixed results
# ---------------------------------------------------------------------------


class TestMixedResults:
    def test_mixed_active_duplicate_possible_duplicate(self) -> None:
        """A batch with all three outcomes in one pass."""
        upload_id = str(uuid.uuid4())

        # Row A — exact match against existing → DUPLICATE
        existing_a = _make_existing(upload_id=upload_id, symbol="NVDA")
        row_a = _make_row(symbol="NVDA")

        # Row B — partial match on 4-field key, different description → POSSIBLE_DUPLICATE
        existing_b = _make_existing(
            symbol="AAPL", description="DIFFERENT", amount=Decimal("100.00")
        )
        row_b = _make_row(symbol="AAPL", amount=Decimal("100.00"))

        # Row C — completely new → ACTIVE
        row_c = _make_row(
            symbol="TSLA",
            amount=Decimal("999.00"),
            trade_date=date(2026, 2, 1),
        )

        results = deduplicate_rows([row_a, row_b, row_c], [existing_a, existing_b])

        assert results[0].status == RawTransactionStatus.DUPLICATE
        assert results[0].matched_upload_id == upload_id

        assert results[1].status == RawTransactionStatus.POSSIBLE_DUPLICATE
        assert results[1].matched_upload_id is None

        assert results[2].status == RawTransactionStatus.ACTIVE
        assert results[2].matched_upload_id is None

    def test_result_list_length_matches_input(self) -> None:
        rows = [
            _make_row(symbol="A", amount=Decimal("1.00")),
            _make_row(symbol="B", amount=Decimal("2.00")),
            _make_row(symbol="C", amount=Decimal("3.00")),
        ]
        results = deduplicate_rows(rows, [])
        assert len(results) == len(rows)

    def test_duplicate_existing_entries_first_upload_wins(self) -> None:
        """If the same composite key appears twice in existing_transactions, the
        first upload_id in the list is recorded (first-upload-wins semantics)."""
        owner_id = str(uuid.uuid4())
        second_id = str(uuid.uuid4())
        existing = [
            _make_existing(upload_id=owner_id),
            _make_existing(upload_id=second_id),  # same composite key, different upload
        ]
        results = deduplicate_rows([_make_row()], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE
        assert results[0].matched_upload_id == owner_id


# ---------------------------------------------------------------------------
# Test: Decimal precision matching
# ---------------------------------------------------------------------------


class TestDecimalPrecisionMatching:
    def test_exact_decimal_quantity_match(self) -> None:
        """Decimal('0.21300') must match Decimal('0.21300') exactly."""
        existing = [_make_existing(quantity=Decimal("0.21300"))]
        results = deduplicate_rows([_make_row(quantity=Decimal("0.21300"))], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE

    def test_different_decimal_precision_does_not_match(self) -> None:
        """Decimal('1.0') must not match Decimal('1.00000') when values differ."""
        existing = [_make_existing(quantity=Decimal("2.00000"))]
        results = deduplicate_rows([_make_row(quantity=Decimal("1.00000"))], existing)
        # different qty → partial key (qty included) → check 4-field partial
        # The 4-field partial uses same trade_date+symbol+amount but different qty
        assert results[0].status == RawTransactionStatus.ACTIVE

    def test_decimal_amount_exact_match(self) -> None:
        existing = [_make_existing(amount=Decimal("250.0000"))]
        results = deduplicate_rows([_make_row(amount=Decimal("250.0000"))], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE

    def test_fractional_quantity_matches_stored_value(self) -> None:
        """Fractional equity quantity (D21) — Decimal('0.12345') must match exactly."""
        frac = Decimal("0.12345")
        existing = [_make_existing(quantity=frac)]
        results = deduplicate_rows([_make_row(quantity=frac)], existing)
        assert results[0].status == RawTransactionStatus.DUPLICATE


# ---------------------------------------------------------------------------
# Test: DeduplicationResult dataclass structure
# ---------------------------------------------------------------------------


class TestDeduplicationResultStructure:
    def test_result_has_row_field(self) -> None:
        row = _make_row()
        result = deduplicate_rows([row], [])
        assert hasattr(result[0], "row")

    def test_result_has_status_field(self) -> None:
        row = _make_row()
        result = deduplicate_rows([row], [])
        assert hasattr(result[0], "status")

    def test_result_has_matched_upload_id_field(self) -> None:
        row = _make_row()
        result = deduplicate_rows([row], [])
        assert hasattr(result[0], "matched_upload_id")

    def test_result_is_deduplication_result_instance(self) -> None:
        row = _make_row()
        result = deduplicate_rows([row], [])
        assert isinstance(result[0], DeduplicationResult)
