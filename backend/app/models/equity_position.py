"""SQLAlchemy ORM model for the EquityPosition entity."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EquityPositionSource, EquityPositionStatus

if TYPE_CHECKING:
    from app.models.options_position import OptionsPosition
    from app.models.transaction import Transaction


class EquityPosition(Base):
    """Represents an equity share lot acquired via purchase, assignment, or exercise."""

    __tablename__ = "equity_positions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 5), nullable=False)
    cost_basis_per_share: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    source: Mapped[EquityPositionSource] = mapped_column(
        Enum(EquityPositionSource, name="equity_position_source"),
        nullable=False,
    )
    # FK to the options position that generated this lot (assignment/exercise only)
    assigned_position_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("options_positions.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
    status: Mapped[EquityPositionStatus] = mapped_column(
        Enum(EquityPositionStatus, name="equity_position_status"),
        nullable=False,
        default=EquityPositionStatus.OPEN,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    equity_realized_pnl: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        default=None,
    )
    # FK to the EQUITY_SELL transaction that closed this lot
    close_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationships
    assigned_position: Mapped[OptionsPosition | None] = relationship(
        back_populates="equity_positions",
        foreign_keys=[assigned_position_id],
    )
    close_transaction: Mapped[Transaction | None] = relationship(
        foreign_keys=[close_transaction_id],
    )
