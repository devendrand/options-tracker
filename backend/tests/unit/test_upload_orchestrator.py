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
- Cover: matcher integration — OptionsPosition, OptionsPositionLeg, EquityPosition creation
- Cover: P&L calculation wired into closed positions
- Cover: covered call detection stamped on SHORT CALL positions
- Cover: _build_transaction_inputs helpers
- Cover: _persist_match_result helpers
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import (
    EquityPositionSource,
    EquityPositionStatus,
    LegRole,
    OptionsPositionStatus,
    TransactionCategory,
)
from app.models.equity_position import EquityPosition
from app.models.options_position import OptionsPosition
from app.models.options_position_leg import OptionsPositionLeg
from app.services.parser.etrade import ParsedRow
from app.services.upload_orchestrator import (
    UploadResult,
    _build_option_symbol,
    _build_transaction_inputs,
    _fetch_existing_transactions,
    _persist_match_result,
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


def _options_close_row(
    transaction_date: str = "03/20/26",
    description: str = "CALL NVDA 06/18/26 220.00",
    symbol: str = "NVDA",
    quantity: str = "1",
    price: str = "1.00",
    amount: str = "-100.00",
    commission: str = "0.65",
    settlement_date: str = "03/22/26",
) -> str:
    """Build a CSV row that classifies as OPTIONS_BUY_TO_CLOSE ('Bought To Cover' + options)."""
    return (
        f"{transaction_date},Bought To Cover,{description},{symbol},"
        f"{quantity},{price},{amount},{commission},{settlement_date}\n"
    )


# ---------------------------------------------------------------------------
# _build_transaction_inputs
# ---------------------------------------------------------------------------


class TestBuildTransactionInputs:
    """Tests for the _build_transaction_inputs helper."""

    def _make_options_txn(self) -> "Transaction":
        from app.models.transaction import Transaction

        txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 3, 15),
            transaction_date=date(2026, 3, 15),
            symbol="NVDA",
            action="Sold Short",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("250.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        txn.option_type = "CALL"
        txn.strike = Decimal("220.00")
        txn.expiry = date(2026, 6, 18)
        txn.price = Decimal("2.50")
        return txn

    def _make_equity_txn(self) -> "Transaction":
        from app.models.transaction import Transaction

        txn = Transaction(
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
        txn.option_type = None
        txn.strike = None
        txn.expiry = None
        txn.price = Decimal("105.00")
        return txn

    def test_options_txn_has_options_fields_set(self) -> None:
        from app.services.matcher import TransactionInput

        txn = self._make_options_txn()
        active_txns = [(0, txn)]
        categories = [TransactionCategory.OPTIONS_SELL_TO_OPEN]

        result = _build_transaction_inputs(active_txns, categories)

        assert len(result) == 1
        ti = result[0]
        assert isinstance(ti, TransactionInput)
        assert ti.index == 0
        assert ti.category == TransactionCategory.OPTIONS_SELL_TO_OPEN
        assert ti.underlying == "NVDA"
        assert ti.option_type == "CALL"
        assert ti.strike == Decimal("220.00")
        assert ti.expiry == date(2026, 6, 18)

    def test_equity_txn_has_no_options_fields(self) -> None:
        txn = self._make_equity_txn()
        active_txns = [(0, txn)]
        categories = [TransactionCategory.EQUITY_BUY]

        result = _build_transaction_inputs(active_txns, categories)

        assert len(result) == 1
        ti = result[0]
        assert ti.underlying is None
        assert ti.option_type is None
        assert ti.strike is None
        assert ti.expiry is None

    def test_local_index_is_position_in_active_txns(self) -> None:
        opt = self._make_options_txn()
        eq = self._make_equity_txn()
        active_txns = [(0, eq), (1, opt)]
        categories = [TransactionCategory.EQUITY_BUY, TransactionCategory.OPTIONS_SELL_TO_OPEN]

        result = _build_transaction_inputs(active_txns, categories)

        assert result[0].index == 0
        assert result[1].index == 1

    def test_option_type_enum_is_coerced_to_str(self) -> None:
        """option_type on Transaction may be OptionType enum (post-DB roundtrip)."""
        from app.models.enums import OptionType

        txn = self._make_options_txn()
        txn.option_type = OptionType.CALL  # type: ignore[assignment]
        active_txns = [(0, txn)]
        categories = [TransactionCategory.OPTIONS_SELL_TO_OPEN]

        result = _build_transaction_inputs(active_txns, categories)

        assert result[0].option_type == "CALL"

    def test_empty_active_txns_returns_empty_list(self) -> None:
        assert _build_transaction_inputs([], []) == []


# ---------------------------------------------------------------------------
# _persist_match_result
# ---------------------------------------------------------------------------


class TestPersistMatchResult:
    """Tests for the _persist_match_result helper."""

    def _make_session(self) -> MagicMock:
        return _make_session()

    def _make_options_txn(
        self,
        *,
        transaction_date: date = date(2026, 3, 15),
        quantity: Decimal = Decimal("1"),
        price: Decimal = Decimal("2.50"),
        amount: Decimal = Decimal("250.00"),
        commission: Decimal = Decimal("0.65"),
        option_type: str = "CALL",
        strike: Decimal = Decimal("220.00"),
        expiry: date = date(2026, 6, 18),
        symbol: str = "NVDA",
    ) -> "Transaction":
        from app.models.transaction import Transaction

        txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=transaction_date,
            transaction_date=transaction_date,
            symbol=symbol,
            action="Sold Short",
            quantity=quantity,
            commission=commission,
            amount=amount,
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        txn.option_type = option_type
        txn.strike = strike
        txn.expiry = expiry
        txn.price = price
        return txn

    def _make_equity_txn(
        self,
        *,
        transaction_date: date = date(2026, 3, 15),
        quantity: Decimal = Decimal("100"),
        price: Decimal = Decimal("200.00"),
        amount: Decimal = Decimal("-20000.00"),
        commission: Decimal = Decimal("0.00"),
        symbol: str = "NVDA",
    ) -> "Transaction":
        from app.models.transaction import Transaction

        txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=transaction_date,
            transaction_date=transaction_date,
            symbol=symbol,
            action="Bought",
            quantity=quantity,
            commission=commission,
            amount=amount,
            category=TransactionCategory.EQUITY_BUY,
        )
        txn.option_type = None
        txn.strike = None
        txn.expiry = None
        txn.price = price
        return txn

    async def test_open_only_creates_options_position_and_leg(self) -> None:
        """A single STO transaction creates one OptionsPosition + one OptionsPositionLeg."""
        from app.services.matcher import TransactionInput, match_transactions

        txn = self._make_options_txn()
        active_txns = [(0, txn)]
        categories = [TransactionCategory.OPTIONS_SELL_TO_OPEN]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        legs = [o for o in added if isinstance(o, OptionsPositionLeg)]
        assert len(positions) == 1
        assert len(legs) == 1
        assert positions[0].underlying == "NVDA"
        assert positions[0].status == OptionsPositionStatus.OPEN
        assert legs[0].leg_role == LegRole.OPEN

    async def test_open_position_has_no_pnl(self) -> None:
        """An OPEN position (no close legs) has realized_pnl=None."""
        from app.services.matcher import match_transactions

        txn = self._make_options_txn()
        active_txns = [(0, txn)]
        categories = [TransactionCategory.OPTIONS_SELL_TO_OPEN]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert positions[0].realized_pnl is None

    async def test_closed_position_has_pnl_set(self) -> None:
        """STO + BTC in same batch produces a CLOSED position with realized_pnl."""
        from app.services.matcher import TransactionInput, match_transactions
        from app.models.transaction import Transaction

        # STO: sell 1 contract for $250 premium
        sto_txn = self._make_options_txn(
            transaction_date=date(2026, 3, 15),
            amount=Decimal("250.00"),
            commission=Decimal("0.65"),
            price=Decimal("2.50"),
        )
        # BTC: buy back for $100, closing the position
        btc_txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 3, 20),
            transaction_date=date(2026, 3, 20),
            symbol="NVDA",
            action="Bought To Cover",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("-100.00"),
            category=TransactionCategory.OPTIONS_BUY_TO_CLOSE,
        )
        btc_txn.option_type = "CALL"
        btc_txn.strike = Decimal("220.00")
        btc_txn.expiry = date(2026, 6, 18)
        btc_txn.price = Decimal("1.00")

        active_txns = [(0, sto_txn), (1, btc_txn)]
        categories = [
            TransactionCategory.OPTIONS_SELL_TO_OPEN,
            TransactionCategory.OPTIONS_BUY_TO_CLOSE,
        ]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        pos = positions[0]
        assert pos.status == OptionsPositionStatus.CLOSED
        # P&L = open_amount + close_amount - commissions = 250 + (-100) - 0.65 - 0.65 = 148.70
        assert pos.realized_pnl == Decimal("148.70")

    async def test_equity_buy_creates_equity_position(self) -> None:
        """An EQUITY_BUY transaction produces an EquityPosition with PURCHASE source."""
        from app.services.matcher import match_transactions

        eq_txn = self._make_equity_txn(quantity=Decimal("100"), price=Decimal("200.00"))
        active_txns = [(0, eq_txn)]
        categories = [TransactionCategory.EQUITY_BUY]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        equity_positions = [o for o in added if isinstance(o, EquityPosition)]
        assert len(equity_positions) == 1
        ep = equity_positions[0]
        assert ep.symbol == "NVDA"
        assert ep.quantity == Decimal("100")
        assert ep.cost_basis_per_share == Decimal("200.00")
        assert ep.source == EquityPositionSource.PURCHASE
        assert ep.status == EquityPositionStatus.OPEN
        assert ep.assigned_position_id is None

    async def test_short_call_with_100_shares_is_covered(self) -> None:
        """SHORT CALL with >= 100 shares of underlying → is_covered_call=True."""
        from app.services.matcher import match_transactions

        eq_txn = self._make_equity_txn(quantity=Decimal("100"), price=Decimal("200.00"))
        opt_txn = self._make_options_txn()
        active_txns = [(0, eq_txn), (1, opt_txn)]
        categories = [TransactionCategory.EQUITY_BUY, TransactionCategory.OPTIONS_SELL_TO_OPEN]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        assert positions[0].is_covered_call is True

    async def test_short_call_without_shares_is_not_covered(self) -> None:
        """SHORT CALL with no equity holding → is_covered_call=False."""
        from app.services.matcher import match_transactions

        opt_txn = self._make_options_txn()
        active_txns = [(0, opt_txn)]
        categories = [TransactionCategory.OPTIONS_SELL_TO_OPEN]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        assert positions[0].is_covered_call is False

    async def test_non_short_call_put_position_is_not_covered(self) -> None:
        """A SHORT PUT position is never stamped as a covered call."""
        from app.services.matcher import match_transactions

        put_txn = self._make_options_txn(option_type="PUT")
        active_txns = [(0, put_txn)]
        categories = [TransactionCategory.OPTIONS_SELL_TO_OPEN]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        assert positions[0].is_covered_call is False

    async def test_empty_match_result_adds_nothing(self) -> None:
        """Non-options, non-equity rows (e.g., DIVIDEND) produce no positions or lots."""
        from app.services.matcher import MatchResult

        match_result = MatchResult(positions=[], equity_lots=[])
        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, [])

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        equity_positions = [o for o in added if isinstance(o, EquityPosition)]
        assert positions == []
        assert equity_positions == []

    async def test_scale_in_close_deduplicates_transaction_for_pnl(self) -> None:
        """2 scale-in STO legs closed by 1 BTC transaction — BTC counted once in P&L."""
        from app.services.matcher import match_transactions
        from app.models.transaction import Transaction

        # STO1: 1 contract
        sto1 = self._make_options_txn(
            transaction_date=date(2026, 3, 10),
            amount=Decimal("250.00"),
            commission=Decimal("0.65"),
        )
        # STO2: 1 contract (scale-in, same contract, later date)
        sto2 = self._make_options_txn(
            transaction_date=date(2026, 3, 12),
            amount=Decimal("240.00"),
            commission=Decimal("0.65"),
        )
        # BTC: 2 contracts (closes both open legs at once)
        btc = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 3, 20),
            transaction_date=date(2026, 3, 20),
            symbol="NVDA",
            action="Bought To Cover",
            quantity=Decimal("2"),
            commission=Decimal("1.30"),
            amount=Decimal("-200.00"),
            category=TransactionCategory.OPTIONS_BUY_TO_CLOSE,
        )
        btc.option_type = "CALL"
        btc.strike = Decimal("220.00")
        btc.expiry = date(2026, 6, 18)
        btc.price = Decimal("1.00")

        active_txns = [(0, sto1), (1, sto2), (2, btc)]
        categories = [
            TransactionCategory.OPTIONS_SELL_TO_OPEN,
            TransactionCategory.OPTIONS_SELL_TO_OPEN,
            TransactionCategory.OPTIONS_BUY_TO_CLOSE,
        ]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        pos = positions[0]
        assert pos.status == OptionsPositionStatus.CLOSED
        # BTC transaction (index 2) appears twice in legs (matched both STO1 and STO2)
        # but must be counted once in P&L.
        # P&L = 250 + 240 + (-200) - 0.65 - 0.65 - 1.30 = 287.40
        assert pos.realized_pnl == Decimal("287.40")

    async def test_closed_equity_lot_not_added_to_holdings(self) -> None:
        """A CLOSED equity lot (result of EQUITY_SELL in same batch) does not count
        toward equity holdings for covered call detection."""
        from app.services.matcher import EquityLot, MatchResult

        closed_lot = EquityLot(
            symbol="NVDA",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("200.00"),
            source=EquityPositionSource.PURCHASE,
            status=EquityPositionStatus.CLOSED,
            from_position_index=None,
            close_transaction_index=1,
        )
        # Also add a SHORT CALL position that would be covered if shares were counted
        from app.services.matcher import MatchedLeg, MatchedPosition
        from app.models.enums import OptionsPositionStatus, PositionDirection

        open_pos = MatchedPosition(
            underlying="NVDA",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type="CALL",
            direction=PositionDirection.SHORT,
            status=OptionsPositionStatus.OPEN,
            legs=[MatchedLeg(transaction_index=0, leg_role=LegRole.OPEN, quantity=Decimal("1"))],
        )
        sto = self._make_options_txn()
        active_txns = [(0, sto), (1, sto)]  # index 1 is a placeholder for the equity sell
        match_result = MatchResult(positions=[open_pos], equity_lots=[closed_lot])

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        # Closed lot → shares NOT added to holdings → SHORT CALL NOT covered
        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        assert positions[0].is_covered_call is False

    async def test_closed_position_has_two_legs(self) -> None:
        """A fully closed position has exactly one OPEN + one CLOSE leg."""
        from app.services.matcher import match_transactions
        from app.models.transaction import Transaction

        sto_txn = self._make_options_txn(
            transaction_date=date(2026, 3, 15),
        )
        btc_txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 3, 20),
            transaction_date=date(2026, 3, 20),
            symbol="NVDA",
            action="Bought To Cover",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("-100.00"),
            category=TransactionCategory.OPTIONS_BUY_TO_CLOSE,
        )
        btc_txn.option_type = "CALL"
        btc_txn.strike = Decimal("220.00")
        btc_txn.expiry = date(2026, 6, 18)
        btc_txn.price = Decimal("1.00")

        active_txns = [(0, sto_txn), (1, btc_txn)]
        categories = [
            TransactionCategory.OPTIONS_SELL_TO_OPEN,
            TransactionCategory.OPTIONS_BUY_TO_CLOSE,
        ]
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)

        session = _make_session()
        added: list[object] = []
        session.add.side_effect = added.append

        await _persist_match_result(session, match_result, active_txns)

        legs = [o for o in added if isinstance(o, OptionsPositionLeg)]
        assert len(legs) == 2
        roles = {leg.leg_role for leg in legs}
        assert LegRole.OPEN in roles
        assert LegRole.CLOSE in roles


# ---------------------------------------------------------------------------
# process_upload — matcher integration (end-to-end via mocked session)
# ---------------------------------------------------------------------------


class TestProcessUploadMatcherIntegration:
    """End-to-end tests verifying matcher/P&L/covered-call wiring in process_upload."""

    @pytest.mark.asyncio
    async def test_options_open_creates_position(self) -> None:
        """An options STO row causes an OptionsPosition to be added to the session."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        added: list[object] = []
        session.add.side_effect = added.append

        csv_content = _make_csv(_options_row())
        await process_upload(session, filename="sto.csv", csv_content=csv_content)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        assert positions[0].underlying == "NVDA"
        assert positions[0].status == OptionsPositionStatus.OPEN

    @pytest.mark.asyncio
    async def test_options_open_creates_open_leg(self) -> None:
        """An STO row produces one OptionsPositionLeg with OPEN role."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        added: list[object] = []
        session.add.side_effect = added.append

        csv_content = _make_csv(_options_row())
        await process_upload(session, filename="sto.csv", csv_content=csv_content)

        legs = [o for o in added if isinstance(o, OptionsPositionLeg)]
        assert len(legs) == 1
        assert legs[0].leg_role == LegRole.OPEN

    @pytest.mark.asyncio
    async def test_options_open_close_creates_closed_position_with_pnl(self) -> None:
        """STO + BTC in same CSV produces a CLOSED position with realized_pnl set."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        added: list[object] = []
        session.add.side_effect = added.append

        csv_content = _make_csv(_options_row(), _options_close_row())
        await process_upload(session, filename="open_close.csv", csv_content=csv_content)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        pos = positions[0]
        assert pos.status == OptionsPositionStatus.CLOSED
        assert pos.realized_pnl is not None

    @pytest.mark.asyncio
    async def test_equity_buy_creates_equity_position(self) -> None:
        """An equity buy row produces one EquityPosition with PURCHASE source."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        added: list[object] = []
        session.add.side_effect = added.append

        csv_content = _make_csv(_equity_row())
        await process_upload(session, filename="eq.csv", csv_content=csv_content)

        equity_positions = [o for o in added if isinstance(o, EquityPosition)]
        assert len(equity_positions) == 1
        assert equity_positions[0].source == EquityPositionSource.PURCHASE

    @pytest.mark.asyncio
    async def test_short_call_with_equity_is_covered(self) -> None:
        """SHORT CALL + 100 NVDA shares in same upload → is_covered_call=True."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        added: list[object] = []
        session.add.side_effect = added.append

        # 100 shares of NVDA, then a 1-contract SHORT CALL on NVDA
        equity = _equity_row(quantity="100", price="200.00", amount="-20000.00")
        csv_content = _make_csv(equity, _options_row())
        await process_upload(session, filename="cc.csv", csv_content=csv_content)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        assert positions[0].is_covered_call is True

    @pytest.mark.asyncio
    async def test_short_call_without_equity_is_not_covered(self) -> None:
        """SHORT CALL with no equity in same upload → is_covered_call=False."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        added: list[object] = []
        session.add.side_effect = added.append

        csv_content = _make_csv(_options_row())
        await process_upload(session, filename="naked.csv", csv_content=csv_content)

        positions = [o for o in added if isinstance(o, OptionsPosition)]
        assert len(positions) == 1
        assert positions[0].is_covered_call is False

    @pytest.mark.asyncio
    async def test_empty_csv_produces_no_positions(self) -> None:
        """Empty CSV (header only) → no OptionsPosition, no EquityPosition objects."""
        session = _make_session()
        session.execute.return_value = _scalars_result([])

        added: list[object] = []
        session.add.side_effect = added.append

        csv_content = _PREAMBLE + _HEADER
        await process_upload(session, filename="empty.csv", csv_content=csv_content)

        assert [o for o in added if isinstance(o, OptionsPosition)] == []
        assert [o for o in added if isinstance(o, EquityPosition)] == []

    @pytest.mark.asyncio
    async def test_duplicate_row_produces_no_position(self) -> None:
        """A DUPLICATE row is skipped entirely — no position is created."""
        from app.models.transaction import Transaction

        existing_txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 3, 15),
            transaction_date=date(2026, 3, 15),
            symbol="NVDA",
            action="Sold Short",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("250.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        existing_txn.settlement_date = date(2026, 3, 17)
        existing_txn.description = "CALL NVDA 06/18/26 220.00"
        existing_txn.price = Decimal("2.50")

        session = _make_session()
        session.execute.return_value = _scalars_result([existing_txn])

        added: list[object] = []
        session.add.side_effect = added.append

        csv_content = _make_csv(_options_row())
        await process_upload(session, filename="dup.csv", csv_content=csv_content)

        assert [o for o in added if isinstance(o, OptionsPosition)] == []
