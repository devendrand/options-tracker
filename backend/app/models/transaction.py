"""SQLAlchemy ORM model for the Transaction entity."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import OptionType, TransactionCategory, TransactionStatus

if TYPE_CHECKING:
    from app.models.options_position_leg import OptionsPositionLeg
    from app.models.raw_transaction import RawTransaction
    from app.models.upload import Upload


class Transaction(Base):
    """A parsed and classified transaction record."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index(
            "ix_transactions_upload_symbol_category_date",
            "upload_id",
            "symbol",
            "category",
            "transaction_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    raw_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("raw_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
    )
    broker_name: Mapped[str] = mapped_column(String(50), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    settlement_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    option_symbol: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    strike: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        default=None,
    )
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    option_type: Mapped[OptionType | None] = mapped_column(
        Enum(OptionType, name="option_type"),
        nullable=True,
        default=None,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    # Decimal to support fractional equity shares (D21)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 5), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True, default=None)
    commission: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    category: Mapped[TransactionCategory] = mapped_column(
        Enum(TransactionCategory, name="transaction_category"),
        nullable=False,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status"),
        nullable=False,
        default=TransactionStatus.ACTIVE,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationships
    raw_transaction: Mapped[RawTransaction] = relationship(back_populates="transaction")
    upload: Mapped[Upload] = relationship(back_populates="transactions")
    position_legs: Mapped[list[OptionsPositionLeg]] = relationship(
        back_populates="transaction",
    )
