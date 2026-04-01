"""Unit tests for all SQLAlchemy ORM models.

Coverage strategy:
- Import each model (executes class-body column declarations)
- Verify __tablename__ values
- Verify enum member names and string values
- Instantiate models with required fields to exercise default factories
- Assert column types and nullability on key columns
- No live DB required — pure Python import + attribute inspection
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Index, Numeric, inspect

from app.models import (
    EquityPosition,
    EquityPositionSource,
    EquityPositionStatus,
    LegRole,
    OptionsPosition,
    OptionsPositionLeg,
    OptionsPositionStatus,
    OptionType,
    PositionDirection,
    RawTransaction,
    RawTransactionStatus,
    Transaction,
    TransactionCategory,
    TransactionStatus,
    Upload,
    UploadStatus,
)
from app.models.enums import UploadStatus as UploadStatusDirect

# ---------------------------------------------------------------------------
# Enum: UploadStatus
# ---------------------------------------------------------------------------


class TestUploadStatus:
    def test_members(self) -> None:
        assert UploadStatus.ACTIVE.value == "ACTIVE"
        assert UploadStatus.SOFT_DELETED.value == "SOFT_DELETED"

    def test_member_count(self) -> None:
        assert len(UploadStatus) == 2


# ---------------------------------------------------------------------------
# Enum: RawTransactionStatus
# ---------------------------------------------------------------------------


class TestRawTransactionStatus:
    def test_members(self) -> None:
        assert RawTransactionStatus.ACTIVE.value == "ACTIVE"
        assert RawTransactionStatus.DUPLICATE.value == "DUPLICATE"
        assert RawTransactionStatus.POSSIBLE_DUPLICATE.value == "POSSIBLE_DUPLICATE"
        assert RawTransactionStatus.PARSE_ERROR.value == "PARSE_ERROR"

    def test_member_count(self) -> None:
        assert len(RawTransactionStatus) == 4


# ---------------------------------------------------------------------------
# Enum: TransactionStatus
# ---------------------------------------------------------------------------


class TestTransactionStatus:
    def test_members(self) -> None:
        assert TransactionStatus.ACTIVE.value == "ACTIVE"
        assert TransactionStatus.SOFT_DELETED.value == "SOFT_DELETED"

    def test_member_count(self) -> None:
        assert len(TransactionStatus) == 2


# ---------------------------------------------------------------------------
# Enum: TransactionCategory
# ---------------------------------------------------------------------------


class TestTransactionCategory:
    def test_options_categories(self) -> None:
        assert TransactionCategory.OPTIONS_SELL_TO_OPEN.value == "OPTIONS_SELL_TO_OPEN"
        assert TransactionCategory.OPTIONS_BUY_TO_OPEN.value == "OPTIONS_BUY_TO_OPEN"
        assert TransactionCategory.OPTIONS_BUY_TO_CLOSE.value == "OPTIONS_BUY_TO_CLOSE"
        assert TransactionCategory.OPTIONS_SELL_TO_CLOSE.value == "OPTIONS_SELL_TO_CLOSE"
        assert TransactionCategory.OPTIONS_EXPIRED.value == "OPTIONS_EXPIRED"
        assert TransactionCategory.OPTIONS_ASSIGNED.value == "OPTIONS_ASSIGNED"
        assert TransactionCategory.OPTIONS_EXERCISED.value == "OPTIONS_EXERCISED"

    def test_equity_and_other_categories(self) -> None:
        assert TransactionCategory.EQUITY_BUY.value == "EQUITY_BUY"
        assert TransactionCategory.EQUITY_SELL.value == "EQUITY_SELL"
        assert TransactionCategory.DIVIDEND.value == "DIVIDEND"
        assert TransactionCategory.TRANSFER.value == "TRANSFER"
        assert TransactionCategory.INTEREST.value == "INTEREST"
        assert TransactionCategory.FEE.value == "FEE"
        assert TransactionCategory.JOURNAL.value == "JOURNAL"
        assert TransactionCategory.OTHER.value == "OTHER"

    def test_member_count(self) -> None:
        assert len(TransactionCategory) == 15


# ---------------------------------------------------------------------------
# Enum: OptionType
# ---------------------------------------------------------------------------


class TestOptionType:
    def test_members(self) -> None:
        assert OptionType.CALL.value == "CALL"
        assert OptionType.PUT.value == "PUT"

    def test_member_count(self) -> None:
        assert len(OptionType) == 2


# ---------------------------------------------------------------------------
# Enum: PositionDirection
# ---------------------------------------------------------------------------


class TestPositionDirection:
    def test_members(self) -> None:
        assert PositionDirection.LONG.value == "LONG"
        assert PositionDirection.SHORT.value == "SHORT"

    def test_member_count(self) -> None:
        assert len(PositionDirection) == 2


# ---------------------------------------------------------------------------
# Enum: OptionsPositionStatus
# ---------------------------------------------------------------------------


class TestOptionsPositionStatus:
    def test_members(self) -> None:
        assert OptionsPositionStatus.OPEN.value == "OPEN"
        assert OptionsPositionStatus.PARTIALLY_CLOSED.value == "PARTIALLY_CLOSED"
        assert OptionsPositionStatus.CLOSED.value == "CLOSED"
        assert OptionsPositionStatus.EXPIRED.value == "EXPIRED"
        assert OptionsPositionStatus.ASSIGNED.value == "ASSIGNED"
        assert OptionsPositionStatus.EXERCISED.value == "EXERCISED"

    def test_member_count(self) -> None:
        assert len(OptionsPositionStatus) == 6


# ---------------------------------------------------------------------------
# Enum: LegRole
# ---------------------------------------------------------------------------


class TestLegRole:
    def test_members(self) -> None:
        assert LegRole.OPEN.value == "OPEN"
        assert LegRole.CLOSE.value == "CLOSE"

    def test_member_count(self) -> None:
        assert len(LegRole) == 2


# ---------------------------------------------------------------------------
# Enum: EquityPositionSource
# ---------------------------------------------------------------------------


class TestEquityPositionSource:
    def test_members(self) -> None:
        assert EquityPositionSource.PURCHASE.value == "PURCHASE"
        assert EquityPositionSource.ASSIGNMENT.value == "ASSIGNMENT"
        assert EquityPositionSource.EXERCISE.value == "EXERCISE"

    def test_member_count(self) -> None:
        assert len(EquityPositionSource) == 3


# ---------------------------------------------------------------------------
# Enum: EquityPositionStatus
# ---------------------------------------------------------------------------


class TestEquityPositionStatus:
    def test_members(self) -> None:
        assert EquityPositionStatus.OPEN.value == "OPEN"
        assert EquityPositionStatus.CLOSED.value == "CLOSED"

    def test_member_count(self) -> None:
        assert len(EquityPositionStatus) == 2


# ---------------------------------------------------------------------------
# Enum: direct import alias coverage
# ---------------------------------------------------------------------------


def test_upload_status_direct_import_alias() -> None:
    """Verify that the direct import from enums module works correctly."""
    assert UploadStatusDirect.ACTIVE is UploadStatus.ACTIVE


# ---------------------------------------------------------------------------
# Model: Upload
# ---------------------------------------------------------------------------


class TestUploadModel:
    def test_tablename(self) -> None:
        assert Upload.__tablename__ == "uploads"

    def test_instantiation_with_required_fields(self) -> None:
        record = Upload(filename="TxnHistory_2026.csv")
        assert record.filename == "TxnHistory_2026.csv"

    def test_default_broker_column_default(self) -> None:
        """broker column default is 'etrade' at the SQL level."""
        col = Upload.__table__.c["broker"]
        assert col.default is not None
        assert col.default.arg == "etrade"

    def test_default_counts_column_defaults(self) -> None:
        """Count columns carry 0 as their column-level default."""
        for col_name in [
            "row_count",
            "options_count",
            "duplicate_count",
            "possible_duplicate_count",
            "parse_error_count",
            "internal_transfer_count",
        ]:
            col = Upload.__table__.c[col_name]
            assert col.default is not None, f"{col_name} has no default"
            assert col.default.arg == 0, f"{col_name} default != 0"

    def test_default_status_column_default(self) -> None:
        """status column default is UploadStatus.ACTIVE."""
        col = Upload.__table__.c["status"]
        assert col.default is not None
        assert col.default.arg == UploadStatus.ACTIVE

    def test_default_deleted_at_is_none(self) -> None:
        record = Upload(filename="test.csv")
        assert record.deleted_at is None

    def test_id_column_has_callable_default(self) -> None:
        """id column default is a callable (uuid4)."""
        col = Upload.__table__.c["id"]
        assert col.default is not None
        assert callable(col.default.arg)

    def test_explicit_id_assignment(self) -> None:
        fixed_id = uuid.uuid4()
        record = Upload(id=fixed_id, filename="test.csv")
        assert record.id == fixed_id

    def test_all_fields_assignable(self) -> None:
        now = datetime(2026, 3, 30, 12, 0, 0)
        record = Upload(
            filename="TxnHistory.csv",
            broker="etrade",
            uploaded_at=now,
            row_count=100,
            options_count=20,
            duplicate_count=3,
            possible_duplicate_count=1,
            parse_error_count=2,
            internal_transfer_count=4,
            status=UploadStatus.SOFT_DELETED,
            deleted_at=now,
        )
        assert record.row_count == 100
        assert record.status == UploadStatus.SOFT_DELETED
        assert record.deleted_at == now

    def test_status_column_type(self) -> None:
        col = Upload.__table__.c["status"]
        assert isinstance(col.type, SAEnum)

    def test_id_column_is_primary_key(self) -> None:
        col = Upload.__table__.c["id"]
        assert col.primary_key is True

    def test_deleted_at_is_nullable(self) -> None:
        col = Upload.__table__.c["deleted_at"]
        assert col.nullable is True


# ---------------------------------------------------------------------------
# Model: RawTransaction
# ---------------------------------------------------------------------------


class TestRawTransactionModel:
    def test_tablename(self) -> None:
        assert RawTransaction.__tablename__ == "raw_transactions"

    def test_instantiation(self) -> None:
        upload_id = uuid.uuid4()
        record = RawTransaction(
            upload_id=upload_id,
            raw_data={"Activity Type": "Dividend", "Symbol": "AAPL"},
        )
        assert record.upload_id == upload_id
        assert record.raw_data["Symbol"] == "AAPL"

    def test_default_is_internal_transfer_column_default(self) -> None:
        """is_internal_transfer column default is False at the SQL level."""
        col = RawTransaction.__table__.c["is_internal_transfer"]
        assert col.default is not None
        assert col.default.arg is False

    def test_default_status_column_default(self) -> None:
        """status column default is ACTIVE at the SQL level."""
        col = RawTransaction.__table__.c["status"]
        assert col.default is not None
        assert col.default.arg == RawTransactionStatus.ACTIVE

    def test_id_column_has_callable_default(self) -> None:
        """id column default is a callable (uuid4)."""
        col = RawTransaction.__table__.c["id"]
        assert col.default is not None
        assert callable(col.default.arg)

    def test_status_column_type(self) -> None:
        col = RawTransaction.__table__.c["status"]
        assert isinstance(col.type, SAEnum)

    def test_upload_id_is_not_nullable(self) -> None:
        col = RawTransaction.__table__.c["upload_id"]
        assert col.nullable is False

    def test_is_internal_transfer_column_not_nullable(self) -> None:
        col = RawTransaction.__table__.c["is_internal_transfer"]
        assert col.nullable is False


# ---------------------------------------------------------------------------
# Model: Transaction
# ---------------------------------------------------------------------------


class TestTransactionModel:
    def test_tablename(self) -> None:
        assert Transaction.__tablename__ == "transactions"

    def test_instantiation(self) -> None:
        today = date(2026, 3, 30)
        record = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=today,
            transaction_date=today,
            symbol="NVDA",
            action="Sold Short",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("200.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        assert record.symbol == "NVDA"
        assert record.quantity == Decimal("1")

    def test_default_status_column_default(self) -> None:
        """status column default is ACTIVE at the SQL level."""
        col = Transaction.__table__.c["status"]
        assert col.default is not None
        assert col.default.arg == TransactionStatus.ACTIVE

    def test_default_nullable_fields(self) -> None:
        today = date(2026, 3, 30)
        record = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=today,
            transaction_date=today,
            symbol="NVDA",
            action="Sold Short",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("200.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        assert record.broker_transaction_id is None
        assert record.settlement_date is None
        assert record.description is None
        assert record.option_symbol is None
        assert record.strike is None
        assert record.expiry is None
        assert record.option_type is None
        assert record.price is None
        assert record.deleted_at is None

    def test_description_column_nullable_string(self) -> None:
        """description column is nullable with String(500) type."""
        from sqlalchemy import String

        col = Transaction.__table__.c["description"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 500

    def test_description_field_assignable(self) -> None:
        """description can be set and retrieved on an instance."""
        today = date(2026, 3, 30)
        record = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=today,
            transaction_date=today,
            symbol="NVDA",
            action="Sold Short",
            description="CALL NVDA 06/18/26 220.00",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("200.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        assert record.description == "CALL NVDA 06/18/26 220.00"

    def test_quantity_is_decimal(self) -> None:
        """D21: quantity must be Decimal to support fractional equity shares."""
        col = Transaction.__table__.c["quantity"]
        assert isinstance(col.type, Numeric)

    def test_composite_index_exists(self) -> None:
        table = Transaction.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_transactions_upload_symbol_category_date" in index_names

    def test_composite_index_columns(self) -> None:
        table = Transaction.__table__
        composite_idx: Index | None = None
        for idx in table.indexes:
            if idx.name == "ix_transactions_upload_symbol_category_date":
                composite_idx = idx
                break
        assert composite_idx is not None
        col_names = [col.name for col in composite_idx.columns]
        assert col_names == ["upload_id", "symbol", "category", "transaction_date"]

    def test_options_fields_assignable(self) -> None:
        today = date(2026, 3, 30)
        record = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=today,
            transaction_date=today,
            symbol="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            action="Sold Short",
            quantity=Decimal("1"),
            price=Decimal("2.00"),
            commission=Decimal("0.65"),
            amount=Decimal("200.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        assert record.option_type == OptionType.CALL
        assert record.strike == Decimal("220.00")

    def test_fractional_quantity(self) -> None:
        """Fractional equity quantity (D21)."""
        today = date(2026, 3, 30)
        record = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=today,
            transaction_date=today,
            symbol="AAPL",
            action="Bought",
            quantity=Decimal("0.12345"),
            commission=Decimal("0.00"),
            amount=Decimal("-24.69"),
            category=TransactionCategory.EQUITY_BUY,
        )
        assert record.quantity == Decimal("0.12345")


# ---------------------------------------------------------------------------
# Model: OptionsPosition
# ---------------------------------------------------------------------------


class TestOptionsPositionModel:
    def test_tablename(self) -> None:
        assert OptionsPosition.__tablename__ == "options_positions"

    def test_instantiation(self) -> None:
        record = OptionsPosition(
            underlying="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            direction=PositionDirection.SHORT,
        )
        assert record.underlying == "NVDA"
        assert record.direction == PositionDirection.SHORT

    def test_default_status_column_default(self) -> None:
        """status column default is OPEN at the SQL level."""
        col = OptionsPosition.__table__.c["status"]
        assert col.default is not None
        assert col.default.arg == OptionsPositionStatus.OPEN

    def test_default_covered_call_column_default(self) -> None:
        """is_covered_call column default is False at the SQL level."""
        col = OptionsPosition.__table__.c["is_covered_call"]
        assert col.default is not None
        assert col.default.arg is False

    def test_default_nullable_fields(self) -> None:
        record = OptionsPosition(
            underlying="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            direction=PositionDirection.SHORT,
        )
        assert record.realized_pnl is None
        assert record.parent_position_id is None
        assert record.deleted_at is None

    def test_composite_index_exists(self) -> None:
        table = OptionsPosition.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_options_positions_underlying_status_expiry" in index_names

    def test_composite_index_columns(self) -> None:
        table = OptionsPosition.__table__
        composite_idx: Index | None = None
        for idx in table.indexes:
            if idx.name == "ix_options_positions_underlying_status_expiry":
                composite_idx = idx
                break
        assert composite_idx is not None
        col_names = [col.name for col in composite_idx.columns]
        assert col_names == ["underlying", "status", "expiry"]

    def test_put_option(self) -> None:
        record = OptionsPosition(
            underlying="SPY",
            option_symbol="SPY   260424P00600000",
            strike=Decimal("600.00"),
            expiry=date(2026, 4, 24),
            option_type=OptionType.PUT,
            direction=PositionDirection.SHORT,
        )
        assert record.option_type == OptionType.PUT

    def test_all_status_values(self) -> None:
        for status in OptionsPositionStatus:
            record = OptionsPosition(
                underlying="NVDA",
                option_symbol="NVDA  260618C00220000",
                strike=Decimal("220.00"),
                expiry=date(2026, 6, 18),
                option_type=OptionType.CALL,
                direction=PositionDirection.SHORT,
                status=status,
            )
            assert record.status == status

    def test_parent_position_id_is_nullable(self) -> None:
        col = OptionsPosition.__table__.c["parent_position_id"]
        assert col.nullable is True


# ---------------------------------------------------------------------------
# Model: OptionsPositionLeg
# ---------------------------------------------------------------------------


class TestOptionsPositionLegModel:
    def test_tablename(self) -> None:
        assert OptionsPositionLeg.__tablename__ == "options_position_legs"

    def test_instantiation(self) -> None:
        record = OptionsPositionLeg(
            position_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            leg_role=LegRole.OPEN,
            quantity=Decimal("2"),
        )
        assert record.leg_role == LegRole.OPEN
        assert record.quantity == Decimal("2")

    def test_close_leg_role(self) -> None:
        record = OptionsPositionLeg(
            position_id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            leg_role=LegRole.CLOSE,
            quantity=Decimal("1"),
        )
        assert record.leg_role == LegRole.CLOSE

    def test_id_column_has_callable_default(self) -> None:
        """id column default is a callable (uuid4)."""
        col = OptionsPositionLeg.__table__.c["id"]
        assert col.default is not None
        assert callable(col.default.arg)

    def test_position_id_not_nullable(self) -> None:
        col = OptionsPositionLeg.__table__.c["position_id"]
        assert col.nullable is False

    def test_transaction_id_not_nullable(self) -> None:
        col = OptionsPositionLeg.__table__.c["transaction_id"]
        assert col.nullable is False

    def test_fractional_quantity_leg(self) -> None:
        """Quantity on legs is Decimal to match Transaction.quantity (D21)."""
        col = OptionsPositionLeg.__table__.c["quantity"]
        assert isinstance(col.type, Numeric)


# ---------------------------------------------------------------------------
# Model: EquityPosition
# ---------------------------------------------------------------------------


class TestEquityPositionModel:
    def test_tablename(self) -> None:
        assert EquityPosition.__tablename__ == "equity_positions"

    def test_purchase_instantiation(self) -> None:
        record = EquityPosition(
            symbol="AAPL",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("150.00"),
            source=EquityPositionSource.PURCHASE,
        )
        assert record.symbol == "AAPL"
        assert record.source == EquityPositionSource.PURCHASE

    def test_assignment_instantiation(self) -> None:
        pos_id = uuid.uuid4()
        record = EquityPosition(
            symbol="NVDA",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("220.00"),
            source=EquityPositionSource.ASSIGNMENT,
            assigned_position_id=pos_id,
        )
        assert record.source == EquityPositionSource.ASSIGNMENT
        assert record.assigned_position_id == pos_id

    def test_exercise_instantiation(self) -> None:
        record = EquityPosition(
            symbol="NVDA",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("220.00"),
            source=EquityPositionSource.EXERCISE,
        )
        assert record.source == EquityPositionSource.EXERCISE

    def test_default_status_column_default(self) -> None:
        """status column default is EquityPositionStatus.OPEN at the SQL level."""
        col = EquityPosition.__table__.c["status"]
        assert col.default is not None
        assert col.default.arg == EquityPositionStatus.OPEN

    def test_default_nullable_fields(self) -> None:
        record = EquityPosition(
            symbol="AAPL",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("150.00"),
            source=EquityPositionSource.PURCHASE,
        )
        assert record.assigned_position_id is None
        assert record.closed_at is None
        assert record.equity_realized_pnl is None
        assert record.close_transaction_id is None
        assert record.deleted_at is None

    def test_closed_state(self) -> None:
        close_tx_id = uuid.uuid4()
        now = datetime(2026, 3, 30, 12, 0, 0)
        record = EquityPosition(
            symbol="AAPL",
            quantity=Decimal("0"),
            cost_basis_per_share=Decimal("150.00"),
            source=EquityPositionSource.PURCHASE,
            status=EquityPositionStatus.CLOSED,
            closed_at=now,
            equity_realized_pnl=Decimal("500.00"),
            close_transaction_id=close_tx_id,
        )
        assert record.status == EquityPositionStatus.CLOSED
        assert record.equity_realized_pnl == Decimal("500.00")
        assert record.close_transaction_id == close_tx_id

    def test_assigned_position_id_is_nullable(self) -> None:
        col = EquityPosition.__table__.c["assigned_position_id"]
        assert col.nullable is True

    def test_close_transaction_id_is_nullable(self) -> None:
        col = EquityPosition.__table__.c["close_transaction_id"]
        assert col.nullable is True

    def test_quantity_is_numeric(self) -> None:
        col = EquityPosition.__table__.c["quantity"]
        assert isinstance(col.type, Numeric)


# ---------------------------------------------------------------------------
# __init__.py re-exports: verify all symbols are importable
# ---------------------------------------------------------------------------


def test_all_models_importable_from_package() -> None:
    """All model classes and enums are accessible from app.models."""
    import app.models as models_pkg

    assert hasattr(models_pkg, "Upload")
    assert hasattr(models_pkg, "RawTransaction")
    assert hasattr(models_pkg, "Transaction")
    assert hasattr(models_pkg, "OptionsPosition")
    assert hasattr(models_pkg, "OptionsPositionLeg")
    assert hasattr(models_pkg, "EquityPosition")
    assert hasattr(models_pkg, "UploadStatus")
    assert hasattr(models_pkg, "RawTransactionStatus")
    assert hasattr(models_pkg, "TransactionStatus")
    assert hasattr(models_pkg, "TransactionCategory")
    assert hasattr(models_pkg, "OptionType")
    assert hasattr(models_pkg, "PositionDirection")
    assert hasattr(models_pkg, "OptionsPositionStatus")
    assert hasattr(models_pkg, "LegRole")
    assert hasattr(models_pkg, "EquityPositionSource")
    assert hasattr(models_pkg, "EquityPositionStatus")


def test_all_models_registered_on_base_metadata() -> None:
    """All tables are visible in Base.metadata after importing models."""
    from app.core.database import Base

    table_names = set(Base.metadata.tables.keys())
    expected = {
        "uploads",
        "raw_transactions",
        "transactions",
        "options_positions",
        "options_position_legs",
        "equity_positions",
    }
    assert expected.issubset(table_names)


# ---------------------------------------------------------------------------
# Relationship smoke tests (no DB — just verify attribute existence)
# ---------------------------------------------------------------------------


def test_upload_has_raw_transactions_relationship() -> None:
    mapper = inspect(Upload)
    assert "raw_transactions" in {r.key for r in mapper.relationships}


def test_upload_has_transactions_relationship() -> None:
    mapper = inspect(Upload)
    assert "transactions" in {r.key for r in mapper.relationships}


def test_raw_transaction_has_upload_relationship() -> None:
    mapper = inspect(RawTransaction)
    assert "upload" in {r.key for r in mapper.relationships}


def test_raw_transaction_has_transaction_relationship() -> None:
    mapper = inspect(RawTransaction)
    assert "transaction" in {r.key for r in mapper.relationships}


def test_transaction_has_raw_transaction_relationship() -> None:
    mapper = inspect(Transaction)
    assert "raw_transaction" in {r.key for r in mapper.relationships}


def test_transaction_has_upload_relationship() -> None:
    mapper = inspect(Transaction)
    assert "upload" in {r.key for r in mapper.relationships}


def test_transaction_has_position_legs_relationship() -> None:
    mapper = inspect(Transaction)
    assert "position_legs" in {r.key for r in mapper.relationships}


def test_options_position_has_legs_relationship() -> None:
    mapper = inspect(OptionsPosition)
    assert "legs" in {r.key for r in mapper.relationships}


def test_options_position_has_equity_positions_relationship() -> None:
    mapper = inspect(OptionsPosition)
    assert "equity_positions" in {r.key for r in mapper.relationships}


def test_options_position_has_self_referential_relationships() -> None:
    mapper = inspect(OptionsPosition)
    rel_keys = {r.key for r in mapper.relationships}
    assert "parent_position" in rel_keys
    assert "child_positions" in rel_keys


def test_options_position_leg_has_position_relationship() -> None:
    mapper = inspect(OptionsPositionLeg)
    assert "position" in {r.key for r in mapper.relationships}


def test_options_position_leg_has_transaction_relationship() -> None:
    mapper = inspect(OptionsPositionLeg)
    assert "transaction" in {r.key for r in mapper.relationships}


def test_equity_position_has_assigned_position_relationship() -> None:
    mapper = inspect(EquityPosition)
    assert "assigned_position" in {r.key for r in mapper.relationships}


def test_equity_position_has_close_transaction_relationship() -> None:
    mapper = inspect(EquityPosition)
    assert "close_transaction" in {r.key for r in mapper.relationships}


# ---------------------------------------------------------------------------
# Inspect: verify pytest fixture absence doesn't break collection
# ---------------------------------------------------------------------------


def test_no_import_side_effects() -> None:
    """Re-importing app.models is idempotent."""
    import importlib

    import app.models as m1

    importlib.reload(m1)
    assert m1.Upload.__tablename__ == "uploads"
