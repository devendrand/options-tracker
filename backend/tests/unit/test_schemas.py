"""Unit tests for all Pydantic response schemas.

Coverage strategy:
- Instantiate each schema with valid data to verify field types
- Verify from_attributes=True works (ORM-to-schema conversion)
- Test optional / nullable fields
- Test nested schemas (OptionsPositionDetailResponse.legs)
- No DB required — pure Pydantic object construction
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import (
    EquityPositionSource,
    EquityPositionStatus,
    LegRole,
    OptionsPositionStatus,
    OptionType,
    PositionDirection,
    TransactionCategory,
    TransactionStatus,
    UploadStatus,
)
from app.schemas.pnl import PnlPeriodResponse, PnlSummaryResponse
from app.schemas.position import (
    EquityPositionResponse,
    OptionsPositionDetailResponse,
    OptionsPositionLegResponse,
    OptionsPositionResponse,
    PositionListResponse,
)
from app.schemas.transaction import TransactionListResponse, TransactionResponse
from app.schemas.upload import (
    UploadDeleteResponse,
    UploadDetailResponse,
    UploadListResponse,
    UploadResponse,
)

# ---------------------------------------------------------------------------
# Helpers: minimal ORM-like object stand-ins
# ---------------------------------------------------------------------------


class _Obj:
    """Minimal attribute bag for testing from_attributes parsing."""

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# UploadResponse
# ---------------------------------------------------------------------------


class TestUploadResponse:
    def _upload_obj(self, **overrides: object) -> _Obj:
        base = dict(
            id=uuid.uuid4(),
            filename="TxnHistory.csv",
            broker="etrade",
            uploaded_at=datetime(2026, 1, 15, 10, 0, 0),
            row_count=50,
            options_count=10,
            duplicate_count=2,
            possible_duplicate_count=1,
            parse_error_count=0,
            internal_transfer_count=3,
            status=UploadStatus.ACTIVE,
        )
        base.update(overrides)
        return _Obj(**base)

    def test_from_attributes_active_upload(self) -> None:
        obj = self._upload_obj()
        resp = UploadResponse.model_validate(obj)
        assert resp.filename == "TxnHistory.csv"
        assert resp.broker == "etrade"
        assert resp.status == UploadStatus.ACTIVE
        assert resp.row_count == 50

    def test_from_attributes_soft_deleted_upload(self) -> None:
        obj = self._upload_obj(status=UploadStatus.SOFT_DELETED)
        resp = UploadResponse.model_validate(obj)
        assert resp.status == UploadStatus.SOFT_DELETED

    def test_direct_construction(self) -> None:
        uid = uuid.uuid4()
        resp = UploadResponse(
            id=uid,
            filename="file.csv",
            broker="etrade",
            uploaded_at=datetime(2026, 3, 1),
            row_count=5,
            options_count=0,
            duplicate_count=0,
            possible_duplicate_count=0,
            parse_error_count=0,
            internal_transfer_count=0,
            status=UploadStatus.ACTIVE,
        )
        assert resp.id == uid


# ---------------------------------------------------------------------------
# UploadDetailResponse
# ---------------------------------------------------------------------------


class TestUploadDetailResponse:
    def test_transaction_count_defaults_to_zero(self) -> None:
        uid = uuid.uuid4()
        resp = UploadDetailResponse(
            id=uid,
            filename="file.csv",
            broker="etrade",
            uploaded_at=datetime(2026, 3, 1),
            row_count=10,
            options_count=5,
            duplicate_count=0,
            possible_duplicate_count=0,
            parse_error_count=0,
            internal_transfer_count=0,
            status=UploadStatus.ACTIVE,
        )
        assert resp.transaction_count == 0

    def test_transaction_count_settable(self) -> None:
        uid = uuid.uuid4()
        resp = UploadDetailResponse(
            id=uid,
            filename="file.csv",
            broker="etrade",
            uploaded_at=datetime(2026, 3, 1),
            row_count=10,
            options_count=5,
            duplicate_count=0,
            possible_duplicate_count=0,
            parse_error_count=0,
            internal_transfer_count=0,
            status=UploadStatus.ACTIVE,
            transaction_count=7,
        )
        assert resp.transaction_count == 7

    def test_inherits_upload_response_fields(self) -> None:
        uid = uuid.uuid4()
        resp = UploadDetailResponse(
            id=uid,
            filename="detail.csv",
            broker="etrade",
            uploaded_at=datetime(2026, 3, 1),
            row_count=10,
            options_count=2,
            duplicate_count=0,
            possible_duplicate_count=0,
            parse_error_count=0,
            internal_transfer_count=1,
            status=UploadStatus.ACTIVE,
        )
        assert resp.broker == "etrade"
        assert resp.options_count == 2


# ---------------------------------------------------------------------------
# UploadListResponse
# ---------------------------------------------------------------------------


class TestUploadListResponse:
    def test_empty_list(self) -> None:
        resp = UploadListResponse(total=0, offset=0, limit=100, items=[])
        assert resp.total == 0
        assert resp.items == []

    def test_with_items(self) -> None:
        uid = uuid.uuid4()
        item = UploadResponse(
            id=uid,
            filename="f.csv",
            broker="etrade",
            uploaded_at=datetime(2026, 3, 1),
            row_count=1,
            options_count=0,
            duplicate_count=0,
            possible_duplicate_count=0,
            parse_error_count=0,
            internal_transfer_count=0,
            status=UploadStatus.ACTIVE,
        )
        resp = UploadListResponse(total=1, offset=0, limit=100, items=[item])
        assert resp.total == 1
        assert len(resp.items) == 1
        assert resp.items[0].id == uid

    def test_pagination_fields(self) -> None:
        resp = UploadListResponse(total=200, offset=50, limit=25, items=[])
        assert resp.offset == 50
        assert resp.limit == 25


# ---------------------------------------------------------------------------
# UploadDeleteResponse
# ---------------------------------------------------------------------------


class TestUploadDeleteResponse:
    def test_with_warning(self) -> None:
        uid = uuid.uuid4()
        resp = UploadDeleteResponse(
            id=uid,
            status=UploadStatus.SOFT_DELETED,
            warning="Some warning",
        )
        assert resp.status == UploadStatus.SOFT_DELETED
        assert resp.warning == "Some warning"

    def test_warning_defaults_to_none(self) -> None:
        uid = uuid.uuid4()
        resp = UploadDeleteResponse(id=uid, status=UploadStatus.SOFT_DELETED)
        assert resp.warning is None

    def test_active_status_allowed(self) -> None:
        uid = uuid.uuid4()
        resp = UploadDeleteResponse(id=uid, status=UploadStatus.ACTIVE)
        assert resp.status == UploadStatus.ACTIVE


# ---------------------------------------------------------------------------
# TransactionResponse
# ---------------------------------------------------------------------------


class TestTransactionResponse:
    def _txn_obj(self, **overrides: object) -> _Obj:
        base = dict(
            id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 1, 15),
            transaction_date=date(2026, 1, 15),
            settlement_date=date(2026, 1, 17),
            symbol="NVDA",
            option_symbol=None,
            strike=None,
            expiry=None,
            option_type=None,
            action="Sold Short",
            description="CALL NVDA 06/18/26 220.00",
            quantity=Decimal("1"),
            price=Decimal("2.50"),
            commission=Decimal("0.65"),
            amount=Decimal("250.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
            status=TransactionStatus.ACTIVE,
            deleted_at=None,
        )
        base.update(overrides)
        return _Obj(**base)

    def test_from_attributes_options_sell_to_open(self) -> None:
        obj = self._txn_obj()
        resp = TransactionResponse.model_validate(obj)
        assert resp.symbol == "NVDA"
        assert resp.category == TransactionCategory.OPTIONS_SELL_TO_OPEN
        assert resp.commission == Decimal("0.65")

    def test_nullable_fields_can_be_none(self) -> None:
        obj = self._txn_obj(
            settlement_date=None,
            option_symbol=None,
            strike=None,
            expiry=None,
            option_type=None,
            description=None,
            price=None,
            deleted_at=None,
        )
        resp = TransactionResponse.model_validate(obj)
        assert resp.settlement_date is None
        assert resp.option_symbol is None
        assert resp.option_type is None

    def test_with_option_fields(self) -> None:
        obj = self._txn_obj(
            option_symbol="NVDA 2026-06-18 CALL 220.0",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
        )
        resp = TransactionResponse.model_validate(obj)
        assert resp.option_type == OptionType.CALL
        assert resp.strike == Decimal("220.00")
        assert resp.expiry == date(2026, 6, 18)

    def test_deleted_at_can_be_set(self) -> None:
        now = datetime(2026, 3, 30, 12, 0, 0)
        obj = self._txn_obj(
            status=TransactionStatus.SOFT_DELETED,
            deleted_at=now,
        )
        resp = TransactionResponse.model_validate(obj)
        assert resp.deleted_at == now
        assert resp.status == TransactionStatus.SOFT_DELETED


# ---------------------------------------------------------------------------
# TransactionListResponse
# ---------------------------------------------------------------------------


class TestTransactionListResponse:
    def test_empty_list(self) -> None:
        resp = TransactionListResponse(total=0, offset=0, limit=100, items=[])
        assert resp.total == 0
        assert resp.items == []

    def test_with_items(self) -> None:
        item = TransactionResponse(
            id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 1, 15),
            transaction_date=date(2026, 1, 15),
            settlement_date=None,
            symbol="AAPL",
            option_symbol=None,
            strike=None,
            expiry=None,
            option_type=None,
            action="Bought",
            description=None,
            quantity=Decimal("10"),
            price=Decimal("150.00"),
            commission=Decimal("0.00"),
            amount=Decimal("-1500.00"),
            category=TransactionCategory.EQUITY_BUY,
            status=TransactionStatus.ACTIVE,
            deleted_at=None,
        )
        resp = TransactionListResponse(total=1, offset=0, limit=100, items=[item])
        assert resp.total == 1
        assert resp.items[0].symbol == "AAPL"


# ---------------------------------------------------------------------------
# OptionsPositionLegResponse
# ---------------------------------------------------------------------------


class TestOptionsPositionLegResponse:
    def _leg_obj(self, **overrides: object) -> _Obj:
        base = dict(
            id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            leg_role=LegRole.OPEN,
            quantity=Decimal("2"),
            trade_date=date(2026, 3, 15),
            price=Decimal("2.50"),
            amount=Decimal("250.00"),
            commission=Decimal("0.65"),
        )
        base.update(overrides)
        return _Obj(**base)

    def test_from_attributes_includes_all_fields(self) -> None:
        obj = self._leg_obj()
        resp = OptionsPositionLegResponse.model_validate(obj)
        assert resp.leg_role == LegRole.OPEN
        assert resp.quantity == Decimal("2")
        assert resp.trade_date == date(2026, 3, 15)
        assert resp.price == Decimal("2.50")
        assert resp.amount == Decimal("250.00")
        assert resp.commission == Decimal("0.65")

    def test_close_role(self) -> None:
        obj = self._leg_obj(leg_role=LegRole.CLOSE, quantity=Decimal("1"))
        resp = OptionsPositionLegResponse.model_validate(obj)
        assert resp.leg_role == LegRole.CLOSE

    def test_price_can_be_none(self) -> None:
        obj = self._leg_obj(price=None)
        resp = OptionsPositionLegResponse.model_validate(obj)
        assert resp.price is None

    def test_from_orm_with_transaction_relationship(self) -> None:
        """Validator lifts trade_date/price/amount/commission from leg.transaction."""
        txn = _Obj(
            trade_date=date(2026, 1, 15),
            price=Decimal("3.00"),
            amount=Decimal("300.00"),
            commission=Decimal("0.65"),
        )
        leg = _Obj(
            id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            leg_role=LegRole.OPEN,
            quantity=Decimal("1"),
            transaction=txn,
        )
        resp = OptionsPositionLegResponse.model_validate(leg)
        assert resp.trade_date == date(2026, 1, 15)
        assert resp.price == Decimal("3.00")
        assert resp.amount == Decimal("300.00")
        assert resp.commission == Decimal("0.65")


# ---------------------------------------------------------------------------
# OptionsPositionResponse
# ---------------------------------------------------------------------------


class TestOptionsPositionResponse:
    def _pos_obj(self, **overrides: object) -> _Obj:
        base = dict(
            id=uuid.uuid4(),
            underlying="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            direction=PositionDirection.SHORT,
            status=OptionsPositionStatus.OPEN,
            realized_pnl=None,
            is_covered_call=False,
        )
        base.update(overrides)
        return _Obj(**base)

    def test_from_attributes_open_position(self) -> None:
        obj = self._pos_obj()
        resp = OptionsPositionResponse.model_validate(obj)
        assert resp.underlying == "NVDA"
        assert resp.status == OptionsPositionStatus.OPEN
        assert resp.realized_pnl is None
        assert resp.is_covered_call is False

    def test_from_attributes_closed_with_pnl(self) -> None:
        obj = self._pos_obj(
            status=OptionsPositionStatus.CLOSED,
            realized_pnl=Decimal("150.00"),
        )
        resp = OptionsPositionResponse.model_validate(obj)
        assert resp.status == OptionsPositionStatus.CLOSED
        assert resp.realized_pnl == Decimal("150.00")

    def test_covered_call_flag(self) -> None:
        obj = self._pos_obj(is_covered_call=True)
        resp = OptionsPositionResponse.model_validate(obj)
        assert resp.is_covered_call is True

    def test_put_option(self) -> None:
        obj = self._pos_obj(
            option_type=OptionType.PUT,
            direction=PositionDirection.LONG,
        )
        resp = OptionsPositionResponse.model_validate(obj)
        assert resp.option_type == OptionType.PUT
        assert resp.direction == PositionDirection.LONG


# ---------------------------------------------------------------------------
# OptionsPositionDetailResponse
# ---------------------------------------------------------------------------


class TestOptionsPositionDetailResponse:
    def _leg_resp(self) -> OptionsPositionLegResponse:
        return OptionsPositionLegResponse(
            id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            leg_role=LegRole.OPEN,
            quantity=Decimal("1"),
            trade_date=date(2026, 3, 15),
            price=Decimal("2.50"),
            amount=Decimal("250.00"),
            commission=Decimal("0.65"),
        )

    def test_with_legs_and_total_pnl(self) -> None:
        legs = [self._leg_resp()]
        detail = OptionsPositionDetailResponse(
            id=uuid.uuid4(),
            underlying="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            direction=PositionDirection.SHORT,
            status=OptionsPositionStatus.CLOSED,
            realized_pnl=Decimal("185.00"),
            is_covered_call=False,
            legs=legs,
            total_realized_pnl=Decimal("185.00"),
        )
        assert len(detail.legs) == 1
        assert detail.legs[0].leg_role == LegRole.OPEN
        assert detail.total_realized_pnl == Decimal("185.00")

    def test_total_realized_pnl_defaults_to_none(self) -> None:
        detail = OptionsPositionDetailResponse(
            id=uuid.uuid4(),
            underlying="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            direction=PositionDirection.SHORT,
            status=OptionsPositionStatus.OPEN,
            realized_pnl=None,
            is_covered_call=False,
            legs=[],
        )
        assert detail.total_realized_pnl is None

    def test_empty_legs_list(self) -> None:
        detail = OptionsPositionDetailResponse(
            id=uuid.uuid4(),
            underlying="SPY",
            option_symbol="SPY   260424P00600000",
            strike=Decimal("600.00"),
            expiry=date(2026, 4, 24),
            option_type=OptionType.PUT,
            direction=PositionDirection.SHORT,
            status=OptionsPositionStatus.EXPIRED,
            realized_pnl=Decimal("-50.00"),
            is_covered_call=False,
            legs=[],
        )
        assert detail.legs == []


# ---------------------------------------------------------------------------
# EquityPositionResponse
# ---------------------------------------------------------------------------


class TestEquityPositionResponse:
    def _eq_obj(self, **overrides: object) -> _Obj:
        base = dict(
            id=uuid.uuid4(),
            symbol="AAPL",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("150.00"),
            status=EquityPositionStatus.OPEN,
            source=EquityPositionSource.PURCHASE,
            equity_realized_pnl=None,
            closed_at=None,
        )
        base.update(overrides)
        return _Obj(**base)

    def test_from_attributes_open_equity_position(self) -> None:
        obj = self._eq_obj()
        resp = EquityPositionResponse.model_validate(obj)
        assert resp.underlying == "AAPL"
        assert resp.status == EquityPositionStatus.OPEN
        assert resp.source == EquityPositionSource.PURCHASE
        assert resp.equity_realized_pnl is None

    def test_from_attributes_closed_with_pnl(self) -> None:
        now = datetime(2026, 3, 30, 12, 0, 0)
        obj = self._eq_obj(
            status=EquityPositionStatus.CLOSED,
            equity_realized_pnl=Decimal("500.00"),
            closed_at=now,
        )
        resp = EquityPositionResponse.model_validate(obj)
        assert resp.status == EquityPositionStatus.CLOSED
        assert resp.equity_realized_pnl == Decimal("500.00")
        assert resp.closed_at == now

    def test_assignment_source(self) -> None:
        obj = self._eq_obj(source=EquityPositionSource.ASSIGNMENT)
        resp = EquityPositionResponse.model_validate(obj)
        assert resp.source == EquityPositionSource.ASSIGNMENT

    def test_exercise_source(self) -> None:
        obj = self._eq_obj(source=EquityPositionSource.EXERCISE)
        resp = EquityPositionResponse.model_validate(obj)
        assert resp.source == EquityPositionSource.EXERCISE


# ---------------------------------------------------------------------------
# PositionListResponse
# ---------------------------------------------------------------------------


class TestPositionListResponse:
    def test_empty_response(self) -> None:
        resp = PositionListResponse(
            total=0,
            offset=0,
            limit=100,
            options_items=[],
            equity_items=[],
        )
        assert resp.total == 0
        assert resp.options_items == []
        assert resp.equity_items == []

    def test_with_options_and_equity(self) -> None:
        opt = OptionsPositionResponse(
            id=uuid.uuid4(),
            underlying="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            direction=PositionDirection.SHORT,
            status=OptionsPositionStatus.OPEN,
            realized_pnl=None,
            is_covered_call=False,
        )
        eq = EquityPositionResponse(
            id=uuid.uuid4(),
            underlying="AAPL",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("150.00"),
            status=EquityPositionStatus.OPEN,
            source=EquityPositionSource.PURCHASE,
            equity_realized_pnl=None,
            closed_at=None,
        )
        resp = PositionListResponse(
            total=2,
            offset=0,
            limit=100,
            options_items=[opt],
            equity_items=[eq],
        )
        assert len(resp.options_items) == 1
        assert len(resp.equity_items) == 1


# ---------------------------------------------------------------------------
# PnlPeriodResponse
# ---------------------------------------------------------------------------


class TestPnlPeriodResponse:
    def test_construction(self) -> None:
        resp = PnlPeriodResponse(
            period_label="2026",
            options_pnl=Decimal("500.00"),
            equity_pnl=Decimal("200.00"),
            total_pnl=Decimal("700.00"),
        )
        assert resp.period_label == "2026"
        assert resp.total_pnl == Decimal("700.00")

    def test_negative_pnl(self) -> None:
        resp = PnlPeriodResponse(
            period_label="2026-01",
            options_pnl=Decimal("-100.00"),
            equity_pnl=Decimal("0.00"),
            total_pnl=Decimal("-100.00"),
        )
        assert resp.options_pnl == Decimal("-100.00")


# ---------------------------------------------------------------------------
# PnlSummaryResponse
# ---------------------------------------------------------------------------


class TestPnlSummaryResponse:
    def test_empty_items(self) -> None:
        resp = PnlSummaryResponse(period="year", items=[])
        assert resp.period == "year"
        assert resp.items == []

    def test_with_items(self) -> None:
        item = PnlPeriodResponse(
            period_label="2026",
            options_pnl=Decimal("300.00"),
            equity_pnl=Decimal("100.00"),
            total_pnl=Decimal("400.00"),
        )
        resp = PnlSummaryResponse(period="year", items=[item])
        assert len(resp.items) == 1
        assert resp.items[0].period_label == "2026"

    def test_month_period(self) -> None:
        resp = PnlSummaryResponse(period="month", items=[])
        assert resp.period == "month"
