"""Unit tests for the upload processing orchestrator.

Coverage strategy:
- Mock AsyncSession to avoid DB dependencies
- Test process_upload() end-to-end with minimal real CSV input
  (the parser and deduplicator are pure functions — no need to mock them)
- Verify UploadResult fields are populated correctly
- Cover: active rows → Transaction created, duplicate/possible_duplicate → only RawTransaction
- Cover: options vs equity category counting
- Cover: internal transfer detection
- Cover: _build_option_symbol for options and non-options rows
- Cover: _fetch_existing_transactions builds correct dict list
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import (
    TransactionCategory,
)
from app.services.parser.etrade import ParsedRow
from app.services.upload_orchestrator import (
    UploadResult,
    _build_option_symbol,
    _fetch_existing_transactions,
    process_upload,
)

# ---------------------------------------------------------------------------
# CSV fixture helpers (identical to test_etrade_parser.py conventions)
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
    return _PREAMBLE + _HEADER + "".join(data_rows)


def _equity_row(
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
    return (
        f"{transaction_date},{activity_type},{description},{symbol},"
        f"{quantity},{price},{amount},{commission},{settlement_date}\n"
    )


def _options_row(
    transaction_date: str = "03/15/26",
    activity_type: str = "Sold Short",
    description: str = "CALL NVDA 06/18/26 220.00",
    symbol: str = "NVDA",
    quantity: str = "1",
    price: str = "2.50",
    amount: str = "250.00",
    commission: str = "0.65",
    settlement_date: str = "03/17/26",
) -> str:
    return (
        f"{transaction_date},{activity_type},{description},{symbol},"
        f"{quantity},{price},{amount},{commission},{settlement_date}\n"
    )


def _transfer_row() -> str:
    return "03/15/26,Transfer,TRNSFR FROM ACCOUNT,--," "--,--,1000.00,,03/17/26\n"


# ---------------------------------------------------------------------------
# Helpers for mocking the AsyncSession
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a mock AsyncSession that records all operations."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


def _scalars_result(items: list[object]) -> MagicMock:
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    return result_mock


# ---------------------------------------------------------------------------
# _build_option_symbol
# ---------------------------------------------------------------------------


class TestBuildOptionSymbol:
    def _make_options_row(self) -> ParsedRow:
        # option_type is str | None in ParsedRow (raw string from parser)
        return ParsedRow(
            transaction_date=date(2026, 3, 15),
            activity_type="Sold Short",
            description="CALL NVDA 06/18/26 220.00",
            symbol="NVDA",
            quantity=Decimal("1"),
            price=Decimal("2.50"),
            amount=Decimal("250.00"),
            commission=Decimal("0.65"),
            settlement_date=date(2026, 3, 17),
            trade_date=date(2026, 3, 15),
            is_option=True,
            underlying="NVDA",
            expiry=date(2026, 6, 18),
            strike=Decimal("220.00"),
            option_type="CALL",
            raw_data={},
        )

    def _make_equity_row(self) -> ParsedRow:
        return ParsedRow(
            transaction_date=date(2026, 3, 15),
            activity_type="Bought",
            description="NVDA",
            symbol="NVDA",
            quantity=Decimal("10"),
            price=Decimal("105.00"),
            amount=Decimal("-1050.00"),
            commission=Decimal("0.00"),
            settlement_date=date(2026, 3, 17),
            trade_date=date(2026, 3, 15),
            is_option=False,
            underlying=None,
            expiry=None,
            strike=None,
            option_type=None,
            raw_data={},
        )

    def test_returns_none_for_non_option(self) -> None:
        row = self._make_equity_row()
        assert _build_option_symbol(row) is None

    def test_returns_formatted_string_for_option(self) -> None:
        row = self._make_options_row()
        result = _build_option_symbol(row)
        assert result is not None
        assert "NVDA" in result
        assert "CALL" in result
        assert "220.00" in result

    def test_handles_missing_underlying(self) -> None:
        row = self._make_options_row()
        row.underlying = None
        result = _build_option_symbol(row)
        # underlying is empty string, joined without it
        assert result is not None

    def test_handles_missing_expiry(self) -> None:
        row = self._make_options_row()
        row.expiry = None
        result = _build_option_symbol(row)
        assert result is not None
        assert "NVDA" in result

    def test_handles_missing_strike(self) -> None:
        row = self._make_options_row()
        row.strike = None
        result = _build_option_symbol(row)
        assert result is not None

    def test_handles_missing_option_type(self) -> None:
        row = self._make_options_row()
        row.option_type = None
        result = _build_option_symbol(row)
        assert result is not None


# ---------------------------------------------------------------------------
# _fetch_existing_transactions
# ---------------------------------------------------------------------------


class TestFetchExistingTransactions:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_transactions(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        result = await _fetch_existing_transactions(session)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_keys(self) -> None:
        from app.models.transaction import Transaction

        txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 1, 15),
            transaction_date=date(2026, 1, 15),
            symbol="NVDA",
            action="Sold Short",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("250.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        txn.settlement_date = None
        txn.description = "CALL NVDA 06/18/26 220.00"
        txn.price = Decimal("2.50")

        session = _make_session()
        session.execute.return_value = _scalars_result([txn])

        result = await _fetch_existing_transactions(session)
        assert len(result) == 1
        row = result[0]
        assert row["trade_date"] == date(2026, 1, 15)
        assert row["transaction_date"] == date(2026, 1, 15)
        assert row["symbol"] == "NVDA"
        assert row["commission"] == Decimal("0.65")
        assert row["activity_type"] == "Sold Short"

    @pytest.mark.asyncio
    async def test_description_defaults_to_empty_string_when_none(self) -> None:
        from app.models.transaction import Transaction

        txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 1, 15),
            transaction_date=date(2026, 1, 15),
            symbol="AAPL",
            action="Bought",
            quantity=Decimal("10"),
            commission=Decimal("0.00"),
            amount=Decimal("-1000.00"),
            category=TransactionCategory.EQUITY_BUY,
        )
        txn.description = None

        session = _make_session()
        session.execute.return_value = _scalars_result([txn])

        result = await _fetch_existing_transactions(session)
        assert result[0]["description"] == ""


# ---------------------------------------------------------------------------
# process_upload
# ---------------------------------------------------------------------------


class TestProcessUpload:
    @pytest.mark.asyncio
    async def test_process_upload_single_equity_row(self) -> None:
        """A single EQUITY_BUY row produces 1 RawTransaction + 1 Transaction."""
        session = _make_session()
        # _fetch_existing_transactions returns empty list
        session.execute.return_value = _scalars_result([])

        csv_content = _make_csv(_equity_row())
        result = await process_upload(session, filename="test.csv", csv_content=csv_content)

        assert isinstance(result, UploadResult)
        assert result.rows_parsed == 1
        assert result.options_count == 0
        assert result.duplicate_count == 0
        assert result.possible_duplicate_count == 0
        assert result.parse_error_count == 0
        assert result.internal_transfer_count == 0
        assert result.upload.filename == "test.csv"
        assert result.upload.row_count == 1

    @pytest.mark.asyncio
    async def test_process_upload_single_options_row(self) -> None:
        """A single OPTIONS_SELL_TO_OPEN row increments options_count."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        csv_content = _make_csv(_options_row())
        result = await process_upload(session, filename="options.csv", csv_content=csv_content)

        assert result.options_count == 1
        assert result.rows_parsed == 1

    @pytest.mark.asyncio
    async def test_process_upload_counts_internal_transfers(self) -> None:
        """Rows with activity_type=Transfer and description starting TRNSFR
        are counted as internal transfers."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        csv_content = _make_csv(_transfer_row())
        result = await process_upload(session, filename="transfer.csv", csv_content=csv_content)

        assert result.internal_transfer_count == 1

    @pytest.mark.asyncio
    async def test_process_upload_duplicate_row_is_stored_as_raw_only(self) -> None:
        """A row that deduplicates against an existing record gets a RawTransaction
        with DUPLICATE status — no Transaction row is created."""
        # Build an existing transaction that matches the incoming row
        from app.models.transaction import Transaction

        existing_txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 3, 15),
            transaction_date=date(2026, 3, 15),
            symbol="NVDA",
            action="Bought",
            quantity=Decimal("10"),
            commission=Decimal("0.00"),
            amount=Decimal("-1050.00"),
            category=TransactionCategory.EQUITY_BUY,
        )
        existing_txn.settlement_date = date(2026, 3, 17)
        existing_txn.description = "NVDA"
        existing_txn.price = Decimal("105.00")

        session = _make_session()
        session.execute.return_value = _scalars_result([existing_txn])

        csv_content = _make_csv(_equity_row())
        result = await process_upload(session, filename="dup.csv", csv_content=csv_content)

        assert result.duplicate_count == 1
        assert result.rows_parsed == 1

    @pytest.mark.asyncio
    async def test_process_upload_empty_csv(self) -> None:
        """An empty CSV (only preamble + header) results in zero rows."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        csv_content = _PREAMBLE + _HEADER
        result = await process_upload(session, filename="empty.csv", csv_content=csv_content)

        assert result.rows_parsed == 0
        assert result.options_count == 0

    @pytest.mark.asyncio
    async def test_process_upload_multiple_rows(self) -> None:
        """Multiple rows: one equity + one options."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        csv_content = _make_csv(_equity_row(), _options_row())
        result = await process_upload(session, filename="mixed.csv", csv_content=csv_content)

        assert result.rows_parsed == 2
        assert result.options_count == 1

    @pytest.mark.asyncio
    async def test_process_upload_sets_broker_to_etrade(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        csv_content = _make_csv(_equity_row())
        result = await process_upload(session, filename="f.csv", csv_content=csv_content)

        assert result.upload.broker == "etrade"

    @pytest.mark.asyncio
    async def test_process_upload_session_add_called_for_upload_and_raw_txn(
        self,
    ) -> None:
        """session.add() must be called for Upload, RawTransaction, Transaction."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        csv_content = _make_csv(_equity_row())
        await process_upload(session, filename="f.csv", csv_content=csv_content)

        # At minimum: Upload + RawTransaction + Transaction = 3 adds
        assert session.add.call_count >= 3

    @pytest.mark.asyncio
    async def test_process_upload_duplicate_row_skips_transaction_add(
        self,
    ) -> None:
        """A DUPLICATE row must NOT produce a Transaction row."""
        from app.models.transaction import Transaction

        existing_txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 3, 15),
            transaction_date=date(2026, 3, 15),
            symbol="NVDA",
            action="Bought",
            quantity=Decimal("10"),
            commission=Decimal("0.00"),
            amount=Decimal("-1050.00"),
            category=TransactionCategory.EQUITY_BUY,
        )
        existing_txn.settlement_date = date(2026, 3, 17)
        existing_txn.description = "NVDA"
        existing_txn.price = Decimal("105.00")

        session = _make_session()
        session.execute.return_value = _scalars_result([existing_txn])

        csv_content = _make_csv(_equity_row())
        await process_upload(session, filename="dup.csv", csv_content=csv_content)

        # Only Upload + RawTransaction = 2 adds (no Transaction)
        added_types = [type(c.args[0]).__name__ for c in session.add.call_args_list]
        assert "Transaction" not in added_types

    @pytest.mark.asyncio
    async def test_process_upload_options_row_builds_option_symbol(self) -> None:
        """Options rows should have option_symbol populated on the Transaction."""
        from app.models.transaction import Transaction as TxnModel

        session = _make_session()
        session.execute.return_value = _scalars_result([])

        # Capture added objects
        added_objects: list[object] = []
        session.add.side_effect = lambda obj: added_objects.append(obj)

        csv_content = _make_csv(_options_row())
        await process_upload(session, filename="opts.csv", csv_content=csv_content)

        txns = [o for o in added_objects if isinstance(o, TxnModel)]
        assert len(txns) == 1
        # option_symbol should be non-None for options rows
        assert txns[0].option_symbol is not None
