"""Unit tests for all repository classes.

Coverage strategy:
- Mock AsyncSession to avoid DB dependencies
- Test every public method on UploadRepository, TransactionRepository,
  PositionRepository, and PnlRepository
- Verify correct query construction (filter application, ordering, pagination)
- Verify correct return types and delegation to session methods
- Cover all code branches (None vs value filters, pnl_type branches, period branches)
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import (
    EquityPositionStatus,
    OptionsPositionStatus,
    TransactionCategory,
    TransactionStatus,
    UploadStatus,
)
from app.repositories.pnl_repository import PnlRepository
from app.repositories.position_repository import PositionRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.upload_repository import UploadRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _async_result(value: object) -> AsyncMock:
    """Return an AsyncMock whose awaited value is *value*."""
    m = AsyncMock()
    m.return_value = value
    return m


def _make_session() -> MagicMock:
    """Return a minimal mock AsyncSession."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


def _scalars_result(items: list[object]) -> MagicMock:
    """Mock that mimics result.scalars().all() returning *items*."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    return result_mock


def _all_result(rows: list[object]) -> MagicMock:
    """Mock that mimics result.all() returning *rows*."""
    result_mock = MagicMock()
    result_mock.all.return_value = rows
    return result_mock


def _first_result(value: object) -> MagicMock:
    """Mock that mimics result.first() returning *value*."""
    result_mock = MagicMock()
    result_mock.first.return_value = value
    return result_mock


def _scalar_one_result(value: object) -> MagicMock:
    """Mock that mimics result.scalar_one() returning *value*."""
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = value
    return result_mock


def _scalar_one_or_none_result(value: object) -> MagicMock:
    """Mock that mimics result.scalar_one_or_none() returning *value*."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = value
    return result_mock


# ---------------------------------------------------------------------------
# UploadRepository
# ---------------------------------------------------------------------------


class TestUploadRepositoryCreate:
    @pytest.mark.asyncio
    async def test_create_adds_and_flushes_and_refreshes(self) -> None:
        session = _make_session()
        repo = UploadRepository(session)

        from app.models.upload import Upload

        upload = Upload(filename="test.csv")
        result = await repo.create(upload)

        session.add.assert_called_once_with(upload)
        session.flush.assert_called_once()
        session.refresh.assert_called_once_with(upload)
        assert result is upload


class TestUploadRepositoryGetById:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_upload_when_found(self) -> None:
        session = _make_session()
        upload_id = uuid.uuid4()

        from app.models.upload import Upload

        mock_upload = Upload(filename="found.csv")
        session.execute.return_value = _scalar_one_or_none_result(mock_upload)

        repo = UploadRepository(session)
        result = await repo.get_by_id(upload_id)

        assert result is mock_upload

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none_result(None)

        repo = UploadRepository(session)
        result = await repo.get_by_id(uuid.uuid4())

        assert result is None


class TestUploadRepositoryListUploads:
    @pytest.mark.asyncio
    async def test_list_uploads_returns_total_and_rows(self) -> None:
        session = _make_session()

        from app.models.upload import Upload

        uploads = [Upload(filename="a.csv"), Upload(filename="b.csv")]

        count_result = _scalar_one_result(2)
        rows_result = _scalars_result(uploads)
        session.execute.side_effect = [count_result, rows_result]

        repo = UploadRepository(session)
        total, rows = await repo.list_uploads()

        assert total == 2
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_list_uploads_respects_offset_and_limit(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = UploadRepository(session)
        total, rows = await repo.list_uploads(offset=10, limit=5)

        assert total == 0
        assert rows == []


class TestUploadRepositorySoftDelete:
    @pytest.mark.asyncio
    async def test_soft_delete_returns_none_when_not_found(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_one_or_none_result(None)

        repo = UploadRepository(session)
        result = await repo.soft_delete(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_soft_delete_marks_upload_and_transactions(self) -> None:
        session = _make_session()
        upload_id = uuid.uuid4()

        from app.models.transaction import Transaction
        from app.models.upload import Upload

        mock_upload = Upload(filename="todelete.csv")
        mock_upload.id = upload_id
        mock_upload.status = UploadStatus.ACTIVE

        mock_txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=upload_id,
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

        # get_by_id call → returns mock_upload
        get_by_id_result = _scalar_one_or_none_result(mock_upload)
        # cascade txn query → returns mock_txn list
        cascade_result = _scalars_result([mock_txn])

        session.execute.side_effect = [get_by_id_result, cascade_result]

        repo = UploadRepository(session)
        result = await repo.soft_delete(upload_id)

        assert result is mock_upload
        assert mock_upload.status == UploadStatus.SOFT_DELETED
        assert mock_txn.status == TransactionStatus.SOFT_DELETED
        assert mock_txn.deleted_at is not None
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_soft_delete_no_active_transactions(self) -> None:
        """soft_delete works even when there are no active transactions."""
        session = _make_session()
        upload_id = uuid.uuid4()

        from app.models.upload import Upload

        mock_upload = Upload(filename="empty.csv")
        mock_upload.id = upload_id
        mock_upload.status = UploadStatus.ACTIVE

        get_by_id_result = _scalar_one_or_none_result(mock_upload)
        cascade_result = _scalars_result([])

        session.execute.side_effect = [get_by_id_result, cascade_result]

        repo = UploadRepository(session)
        result = await repo.soft_delete(upload_id)

        assert result is mock_upload
        assert mock_upload.status == UploadStatus.SOFT_DELETED


class TestUploadRepositoryGetTransactionCount:
    @pytest.mark.asyncio
    async def test_get_transaction_count_returns_scalar(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_one_result(7)

        repo = UploadRepository(session)
        count = await repo.get_transaction_count(uuid.uuid4())

        assert count == 7

    @pytest.mark.asyncio
    async def test_get_transaction_count_zero(self) -> None:
        session = _make_session()
        session.execute.return_value = _scalar_one_result(0)

        repo = UploadRepository(session)
        count = await repo.get_transaction_count(uuid.uuid4())

        assert count == 0


# ---------------------------------------------------------------------------
# TransactionRepository
# ---------------------------------------------------------------------------


class TestTransactionRepositoryListTransactions:
    @pytest.mark.asyncio
    async def test_list_transactions_returns_total_and_rows(self) -> None:
        session = _make_session()

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

        count_result = _scalar_one_result(1)
        rows_result = _scalars_result([txn])
        session.execute.side_effect = [count_result, rows_result]

        repo = TransactionRepository(session)
        total, rows = await repo.list_transactions()

        assert total == 1
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_list_transactions_with_all_filters(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = TransactionRepository(session)
        total, rows = await repo.list_transactions(
            upload_id=uuid.uuid4(),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
            symbol="NVDA",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            offset=5,
            limit=25,
        )

        assert total == 0
        assert rows == []

    @pytest.mark.asyncio
    async def test_list_transactions_no_filters(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = TransactionRepository(session)
        total, rows = await repo.list_transactions()

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_transactions_upload_id_filter_only(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(3)
        rows_result = _scalars_result([MagicMock(), MagicMock(), MagicMock()])
        session.execute.side_effect = [count_result, rows_result]

        repo = TransactionRepository(session)
        total, rows = await repo.list_transactions(upload_id=uuid.uuid4())

        assert total == 3
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_list_transactions_date_from_only(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = TransactionRepository(session)
        total, rows = await repo.list_transactions(date_from=date(2026, 1, 1))

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_transactions_date_to_only(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = TransactionRepository(session)
        total, rows = await repo.list_transactions(date_to=date(2026, 12, 31))

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_transactions_symbol_filter_only(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = TransactionRepository(session)
        total, rows = await repo.list_transactions(symbol="NVDA")

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_transactions_category_filter_only(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = TransactionRepository(session)
        total, rows = await repo.list_transactions(
            category=TransactionCategory.OPTIONS_BUY_TO_CLOSE
        )

        assert total == 0


# ---------------------------------------------------------------------------
# PositionRepository
# ---------------------------------------------------------------------------


class TestPositionRepositoryListOptionsPositions:
    @pytest.mark.asyncio
    async def test_list_options_positions_returns_results(self) -> None:
        session = _make_session()
        mock_pos = MagicMock()
        open_date = date(2026, 1, 15)
        close_date = date(2026, 3, 20)
        count_result = _scalar_one_result(1)
        rows_result = _all_result([(mock_pos, open_date, close_date)])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_options_positions()

        assert total == 1
        assert len(rows) == 1
        pos, o_date, c_date = rows[0]
        assert pos is mock_pos
        assert o_date == open_date
        assert c_date == close_date

    @pytest.mark.asyncio
    async def test_list_options_positions_with_underlying_filter(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _all_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_options_positions(underlying="NVDA")

        assert total == 0
        assert rows == []

    @pytest.mark.asyncio
    async def test_list_options_positions_with_status_filter(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _all_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_options_positions(status=OptionsPositionStatus.OPEN)

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_options_positions_all_filters(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _all_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_options_positions(
            underlying="SPY",
            status=OptionsPositionStatus.CLOSED,
            offset=10,
            limit=50,
        )

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_options_positions_none_dates_when_no_legs(self) -> None:
        """Positions with no open/close legs yield None for both dates."""
        session = _make_session()
        mock_pos = MagicMock()
        count_result = _scalar_one_result(1)
        rows_result = _all_result([(mock_pos, None, None)])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_options_positions()

        assert total == 1
        pos, o_date, c_date = rows[0]
        assert pos is mock_pos
        assert o_date is None
        assert c_date is None


class TestPositionRepositoryGetOptionsPositionDetail:
    @pytest.mark.asyncio
    async def test_returns_position_tuple_when_found(self) -> None:
        session = _make_session()
        mock_pos = MagicMock()
        open_date = date(2026, 1, 10)
        close_date = date(2026, 2, 5)
        session.execute.return_value = _first_result((mock_pos, open_date, close_date))

        repo = PositionRepository(session)
        result = await repo.get_options_position_detail(uuid.uuid4())

        assert result is not None
        pos, o_date, c_date = result
        assert pos is mock_pos
        assert o_date == open_date
        assert c_date == close_date

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        session = _make_session()
        session.execute.return_value = _first_result(None)

        repo = PositionRepository(session)
        result = await repo.get_options_position_detail(uuid.uuid4())

        assert result is None


class TestPositionRepositoryListEquityPositions:
    @pytest.mark.asyncio
    async def test_list_equity_positions_returns_results(self) -> None:
        session = _make_session()
        mock_pos = MagicMock()
        count_result = _scalar_one_result(1)
        rows_result = _scalars_result([mock_pos])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_equity_positions()

        assert total == 1
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_list_equity_positions_with_underlying_filter(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_equity_positions(underlying="AAPL")

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_equity_positions_with_status_filter(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_equity_positions(status=EquityPositionStatus.CLOSED)

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_equity_positions_all_filters(self) -> None:
        session = _make_session()
        count_result = _scalar_one_result(0)
        rows_result = _scalars_result([])
        session.execute.side_effect = [count_result, rows_result]

        repo = PositionRepository(session)
        total, rows = await repo.list_equity_positions(
            underlying="NVDA",
            status=EquityPositionStatus.OPEN,
            offset=5,
            limit=20,
        )

        assert total == 0


# ---------------------------------------------------------------------------
# PnlRepository
# ---------------------------------------------------------------------------


class TestPnlRepository:
    def _make_pnl_session(
        self,
        options_rows: list[tuple[str, str]],
        equity_rows: list[tuple[str, str]],
    ) -> MagicMock:
        """Build a session mock that returns the given rows for both subqueries.

        PnlRepository calls session.execute() twice (once for options, once for
        equity) and then calls .all() on the awaited result.  AsyncMock.return_value
        must be a plain MagicMock (not a coroutine) so that .all() works.
        """
        opts_result = MagicMock()
        opts_result.all.return_value = [MagicMock(lbl=lbl, pnl=pnl) for lbl, pnl in options_rows]
        eq_result = MagicMock()
        eq_result.all.return_value = [MagicMock(lbl=lbl, pnl=pnl) for lbl, pnl in equity_rows]

        session = _make_session()
        # AsyncMock returns an awaitable; its return_value is what you get after await.
        session.execute.side_effect = [opts_result, eq_result]
        return session

    @pytest.mark.asyncio
    async def test_get_pnl_summary_year_all_returns_merged_periods(self) -> None:
        session = self._make_pnl_session(
            options_rows=[("2026", "500.00")],
            equity_rows=[("2026", "200.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="all")

        assert len(results) == 1
        assert results[0].period_label == "2026"
        assert results[0].options_pnl == Decimal("500.00")
        assert results[0].equity_pnl == Decimal("200.00")
        assert results[0].total_pnl == Decimal("700.00")

    @pytest.mark.asyncio
    async def test_get_pnl_summary_options_only_zeros_equity(self) -> None:
        session = self._make_pnl_session(
            options_rows=[("2026", "300.00")],
            equity_rows=[("2026", "100.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="options")

        assert len(results) == 1
        assert results[0].options_pnl == Decimal("300.00")
        assert results[0].equity_pnl == Decimal("0.00")
        assert results[0].total_pnl == Decimal("300.00")

    @pytest.mark.asyncio
    async def test_get_pnl_summary_equity_only_zeros_options(self) -> None:
        session = self._make_pnl_session(
            options_rows=[("2026", "300.00")],
            equity_rows=[("2026", "100.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="equity")

        assert len(results) == 1
        assert results[0].options_pnl == Decimal("0.00")
        assert results[0].equity_pnl == Decimal("100.00")
        assert results[0].total_pnl == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_get_pnl_summary_empty_returns_empty_list(self) -> None:
        session = self._make_pnl_session(options_rows=[], equity_rows=[])
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="all")

        assert results == []

    @pytest.mark.asyncio
    async def test_get_pnl_summary_month_period(self) -> None:
        session = self._make_pnl_session(
            options_rows=[("2026-01", "150.00"), ("2026-02", "250.00")],
            equity_rows=[],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="month", pnl_type="all")

        assert len(results) == 2
        labels = [r.period_label for r in results]
        assert labels == sorted(labels)

    @pytest.mark.asyncio
    async def test_get_pnl_summary_with_underlying_filter(self) -> None:
        session = self._make_pnl_session(
            options_rows=[("2026", "100.00")],
            equity_rows=[],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="all", underlying="NVDA")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_pnl_summary_periods_sorted_ascending(self) -> None:
        session = self._make_pnl_session(
            options_rows=[("2026", "100.00"), ("2024", "50.00"), ("2025", "75.00")],
            equity_rows=[],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="all")

        labels = [r.period_label for r in results]
        assert labels == ["2024", "2025", "2026"]

    @pytest.mark.asyncio
    async def test_get_pnl_summary_missing_period_gets_zero_for_options(self) -> None:
        """A period present only in equity gets 0 for options P&L."""
        session = self._make_pnl_session(
            options_rows=[],
            equity_rows=[("2026", "200.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="all")

        assert len(results) == 1
        assert results[0].options_pnl == Decimal("0.00")
        assert results[0].equity_pnl == Decimal("200.00")

    @pytest.mark.asyncio
    async def test_get_pnl_summary_missing_period_gets_zero_for_equity(self) -> None:
        """A period present only in options gets 0 for equity P&L."""
        session = self._make_pnl_session(
            options_rows=[("2026", "300.00")],
            equity_rows=[],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="all")

        assert len(results) == 1
        assert results[0].equity_pnl == Decimal("0.00")
        assert results[0].options_pnl == Decimal("300.00")

    @pytest.mark.asyncio
    async def test_options_only_pnl_type_excludes_equity_periods(self) -> None:
        """pnl_type='options' only includes periods with options P&L."""
        session = self._make_pnl_session(
            options_rows=[("2026", "100.00")],
            equity_rows=[("2025", "50.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="options")

        assert len(results) == 1
        assert results[0].period_label == "2026"

    @pytest.mark.asyncio
    async def test_equity_only_pnl_type_excludes_options_periods(self) -> None:
        """pnl_type='equity' only includes periods with equity P&L."""
        session = self._make_pnl_session(
            options_rows=[("2026", "100.00")],
            equity_rows=[("2025", "50.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="equity")

        assert len(results) == 1
        assert results[0].period_label == "2025"

    @pytest.mark.asyncio
    async def test_get_pnl_summary_group_by_underlying(self) -> None:
        """group_by='underlying' labels rows by ticker symbol."""
        session = self._make_pnl_session(
            options_rows=[("NVDA", "400.00")],
            equity_rows=[("NVDA", "100.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(period="year", pnl_type="all", group_by="underlying")

        assert len(results) == 1
        assert results[0].period_label == "NVDA"
        assert results[0].options_pnl == Decimal("400.00")
        assert results[0].equity_pnl == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_get_pnl_summary_group_by_period_underlying_year(self) -> None:
        """group_by='period_underlying' produces composite 'YYYY | TICKER' labels."""
        session = self._make_pnl_session(
            options_rows=[("2026 | SPX", "300.00")],
            equity_rows=[],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(
            period="year", pnl_type="all", group_by="period_underlying"
        )

        assert len(results) == 1
        assert results[0].period_label == "2026 | SPX"

    @pytest.mark.asyncio
    async def test_get_pnl_summary_group_by_period_underlying_month(self) -> None:
        """group_by='period_underlying' with period='month' produces 'YYYY-MM | TICKER' labels."""
        session = self._make_pnl_session(
            options_rows=[("2026-03 | SPX", "150.00")],
            equity_rows=[],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(
            period="month", pnl_type="all", group_by="period_underlying"
        )

        assert len(results) == 1
        assert results[0].period_label == "2026-03 | SPX"

    @pytest.mark.asyncio
    async def test_get_pnl_summary_with_closed_after(self) -> None:
        """closed_after date param exercises the date-range filter branch."""
        session = self._make_pnl_session(
            options_rows=[("2026", "100.00")],
            equity_rows=[],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(
            period="year", pnl_type="all", closed_after=date(2026, 1, 1)
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_pnl_summary_with_closed_before(self) -> None:
        """closed_before date param exercises the date-range filter branch."""
        session = self._make_pnl_session(
            options_rows=[("2026", "100.00")],
            equity_rows=[("2026", "50.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(
            period="year", pnl_type="all", closed_before=date(2026, 12, 31)
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_pnl_summary_with_date_range(self) -> None:
        """Both closed_after and closed_before exercise both branches."""
        session = self._make_pnl_session(
            options_rows=[("2026", "200.00")],
            equity_rows=[("2026", "100.00")],
        )
        repo = PnlRepository(session)
        results = await repo.get_pnl_summary(
            period="year",
            pnl_type="all",
            closed_after=date(2026, 1, 1),
            closed_before=date(2026, 6, 30),
        )

        assert len(results) == 1
        assert results[0].total_pnl == Decimal("300.00")


class TestPnlRepositoryGetPositionsForBucket:
    """Tests that get_positions_for_bucket returns tuples for options rows."""

    def _make_bucket_session(
        self,
        opts_count: int,
        opts_rows: list[object],
        eq_count: int,
        eq_rows: list[object],
    ) -> MagicMock:
        """Build a session mock for get_positions_for_bucket.

        options path: count query + rows query (result.all())
        equity path:  count query + rows query (result.scalars().all())
        """
        opts_count_result = _scalar_one_result(opts_count)
        opts_rows_result = _all_result(opts_rows)
        eq_count_result = _scalar_one_result(eq_count)
        eq_rows_result = _scalars_result(eq_rows)

        session = _make_session()
        session.execute.side_effect = [
            opts_count_result,
            opts_rows_result,
            eq_count_result,
            eq_rows_result,
        ]
        return session

    @pytest.mark.asyncio
    async def test_options_rows_are_tuples_with_dates(self) -> None:
        """Options rows in the bucket result are (pos, open_date, close_date) tuples."""
        mock_pos = MagicMock()
        open_date = date(2026, 1, 10)
        close_date = date(2026, 2, 20)
        session = self._make_bucket_session(
            opts_count=1,
            opts_rows=[(mock_pos, open_date, close_date)],
            eq_count=0,
            eq_rows=[],
        )
        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="period",
            period_label="2026",
            pnl_type="all",
            offset=0,
            limit=100,
        )

        assert opts_total == 1
        assert len(opts_rows) == 1
        pos, o_date, c_date = opts_rows[0]
        assert pos is mock_pos
        assert o_date == open_date
        assert c_date == close_date
        assert eq_total == 0
        assert eq_rows == []

    @pytest.mark.asyncio
    async def test_options_rows_none_dates_when_no_legs(self) -> None:
        """Options rows with no legs yield None for both dates."""
        mock_pos = MagicMock()
        session = self._make_bucket_session(
            opts_count=1,
            opts_rows=[(mock_pos, None, None)],
            eq_count=0,
            eq_rows=[],
        )
        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="period",
            period_label="2026",
            pnl_type="all",
            offset=0,
            limit=100,
        )

        assert opts_total == 1
        pos, o_date, c_date = opts_rows[0]
        assert pos is mock_pos
        assert o_date is None
        assert c_date is None

    @pytest.mark.asyncio
    async def test_options_only_type_skips_equity_queries(self) -> None:
        """pnl_type='options' only runs the options path (2 execute calls)."""
        mock_pos = MagicMock()
        open_date = date(2026, 1, 5)
        close_date = date(2026, 3, 10)
        opts_count_result = _scalar_one_result(1)
        opts_rows_result = _all_result([(mock_pos, open_date, close_date)])

        session = _make_session()
        session.execute.side_effect = [opts_count_result, opts_rows_result]

        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="period",
            period_label="2026",
            pnl_type="options",
            offset=0,
            limit=100,
        )

        assert opts_total == 1
        assert eq_total == 0
        assert eq_rows == []
        # Only 2 execute calls (count + rows for options)
        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_underlying_filter_applied_to_options_bucket(self) -> None:
        """group_by='underlying' still returns tuple rows."""
        mock_pos = MagicMock()
        open_date = date(2026, 2, 1)
        opts_count_result = _scalar_one_result(1)
        opts_rows_result = _all_result([(mock_pos, open_date, None)])

        session = _make_session()
        session.execute.side_effect = [opts_count_result, opts_rows_result]

        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="underlying",
            period_label="NVDA",
            pnl_type="options",
            offset=0,
            limit=100,
        )

        assert opts_total == 1
        pos, o_date, c_date = opts_rows[0]
        assert pos is mock_pos
        assert o_date == open_date
        assert c_date is None

    @pytest.mark.asyncio
    async def test_options_bucket_with_additional_underlying_filter(self) -> None:
        """The underlying kwarg adds an extra WHERE clause on top of period filter."""
        mock_pos = MagicMock()
        opts_count_result = _scalar_one_result(1)
        opts_rows_result = _all_result([(mock_pos, None, None)])

        session = _make_session()
        session.execute.side_effect = [opts_count_result, opts_rows_result]

        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="period",
            period_label="2026",
            underlying="NVDA",
            pnl_type="options",
            offset=0,
            limit=100,
        )

        assert opts_total == 1
        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_equity_bucket_group_by_underlying(self) -> None:
        """group_by='underlying' filters equity by symbol label."""
        mock_eq = MagicMock()
        eq_count_result = _scalar_one_result(1)
        eq_rows_result = _scalars_result([mock_eq])

        session = _make_session()
        session.execute.side_effect = [eq_count_result, eq_rows_result]

        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="underlying",
            period_label="AAPL",
            pnl_type="equity",
            offset=0,
            limit=100,
        )

        assert eq_total == 1
        assert eq_rows[0] is mock_eq

    @pytest.mark.asyncio
    async def test_equity_bucket_with_additional_underlying_filter(self) -> None:
        """underlying kwarg adds an extra WHERE on top of period filter for equity."""
        mock_eq = MagicMock()
        eq_count_result = _scalar_one_result(1)
        eq_rows_result = _scalars_result([mock_eq])

        session = _make_session()
        session.execute.side_effect = [eq_count_result, eq_rows_result]

        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="period",
            period_label="2026",
            underlying="AAPL",
            pnl_type="equity",
            offset=0,
            limit=100,
        )

        assert eq_total == 1
        assert session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_options_bucket_with_closed_after(self) -> None:
        """closed_after exercises the date-range branch in options bucket."""
        mock_pos = MagicMock()
        session = self._make_bucket_session(
            opts_count=1,
            opts_rows=[(mock_pos, date(2026, 1, 10), date(2026, 3, 15))],
            eq_count=0,
            eq_rows=[],
        )
        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="period",
            period_label="2026",
            pnl_type="all",
            offset=0,
            limit=100,
            closed_after=date(2026, 1, 1),
        )

        assert opts_total == 1

    @pytest.mark.asyncio
    async def test_options_bucket_with_date_range(self) -> None:
        """Both closed_after and closed_before exercise both branches."""
        mock_pos = MagicMock()
        session = self._make_bucket_session(
            opts_count=1,
            opts_rows=[(mock_pos, date(2026, 1, 10), date(2026, 2, 20))],
            eq_count=1,
            eq_rows=[MagicMock()],
        )
        repo = PnlRepository(session)
        opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
            period="year",
            group_by="period",
            period_label="2026",
            pnl_type="all",
            offset=0,
            limit=100,
            closed_after=date(2026, 1, 1),
            closed_before=date(2026, 6, 30),
        )

        assert opts_total == 1
        assert eq_total == 1


class TestPnlRepositoryGrpLabelHelpers:
    """Unit tests for the pure SQL-expression builder helpers."""

    def test_period_fmt_year(self) -> None:
        repo = PnlRepository(MagicMock())
        assert repo._period_fmt("year") == "YYYY"

    def test_period_fmt_month(self) -> None:
        repo = PnlRepository(MagicMock())
        assert repo._period_fmt("month") == "YYYY-MM"

    def test_build_grp_label_options_period(self) -> None:
        """group_by='period' returns a to_char expression (not the underlying col)."""
        repo = PnlRepository(MagicMock())
        close_col = MagicMock(name="close_date")
        underlying_col = MagicMock(name="underlying")
        result = repo._build_grp_label_options(
            period="year",
            group_by="period",
            close_date_col=close_col,
            underlying_col=underlying_col,
        )
        # Should be a func.to_char expression, not the raw underlying column
        assert result is not underlying_col

    def test_build_grp_label_options_underlying(self) -> None:
        """group_by='underlying' returns the underlying column directly."""
        repo = PnlRepository(MagicMock())
        close_col = MagicMock(name="close_date")
        underlying_col = MagicMock(name="underlying")
        result = repo._build_grp_label_options(
            period="year",
            group_by="underlying",
            close_date_col=close_col,
            underlying_col=underlying_col,
        )
        assert result is underlying_col

    def test_build_grp_label_options_period_underlying(self) -> None:
        """group_by='period_underlying' returns a func.concat expression."""
        repo = PnlRepository(MagicMock())
        close_col = MagicMock(name="close_date")
        underlying_col = MagicMock(name="underlying")
        result = repo._build_grp_label_options(
            period="year",
            group_by="period_underlying",
            close_date_col=close_col,
            underlying_col=underlying_col,
        )
        # Should not be the raw underlying or close_date columns
        assert result is not underlying_col
        assert result is not close_col

    def test_build_grp_label_equity_period(self) -> None:
        """group_by='period' returns a to_char expression for equity."""
        repo = PnlRepository(MagicMock())
        closed_at_col = MagicMock(name="closed_at")
        symbol_col = MagicMock(name="symbol")
        result = repo._build_grp_label_equity(
            period="year",
            group_by="period",
            closed_at_col=closed_at_col,
            symbol_col=symbol_col,
        )
        assert result is not symbol_col

    def test_build_grp_label_equity_underlying(self) -> None:
        """group_by='underlying' returns the symbol column directly for equity."""
        repo = PnlRepository(MagicMock())
        closed_at_col = MagicMock(name="closed_at")
        symbol_col = MagicMock(name="symbol")
        result = repo._build_grp_label_equity(
            period="year",
            group_by="underlying",
            closed_at_col=closed_at_col,
            symbol_col=symbol_col,
        )
        assert result is symbol_col

    def test_build_grp_label_equity_period_underlying(self) -> None:
        """group_by='period_underlying' returns a func.concat expression for equity."""
        repo = PnlRepository(MagicMock())
        closed_at_col = MagicMock(name="closed_at")
        symbol_col = MagicMock(name="symbol")
        result = repo._build_grp_label_equity(
            period="year",
            group_by="period_underlying",
            closed_at_col=closed_at_col,
            symbol_col=symbol_col,
        )
        assert result is not symbol_col
        assert result is not closed_at_col
