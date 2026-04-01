"""SQLAlchemy ORM model for the OptionsPosition entity."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import OptionsPositionStatus, OptionType, PositionDirection

if TYPE_CHECKING:
    from app.models.equity_position import EquityPosition
    from app.models.options_position_leg import OptionsPositionLeg


class OptionsPosition(Base):
    """Represents a single options contract position (one or more legs)."""

    __tablename__ = "options_positions"
    __table_args__ = (
        Index(
            "ix_options_positions_underlying_status_expiry",
            "underlying",
            "status",
            "expiry",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    underlying: Mapped[str] = mapped_column(String(20), nullable=False)
    option_symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    strike: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    option_type: Mapped[OptionType] = mapped_column(
        Enum(OptionType, name="option_type"),
        nullable=False,
    )
    direction: Mapped[PositionDirection] = mapped_column(
        Enum(PositionDirection, name="position_direction"),
        nullable=False,
    )
    status: Mapped[OptionsPositionStatus] = mapped_column(
        Enum(OptionsPositionStatus, name="options_position_status"),
        nullable=False,
        default=OptionsPositionStatus.OPEN,
    )
    realized_pnl: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        default=None,
    )
    is_covered_call: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    # Reserved for v1.0 roll-chain tracking — always null in v0.1
    parent_position_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("options_positions.id", ondelete="SET NULL"),
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
    legs: Mapped[list[OptionsPositionLeg]] = relationship(
        back_populates="position",
    )
    equity_positions: Mapped[list[EquityPosition]] = relationship(
        back_populates="assigned_position",
        foreign_keys="EquityPosition.assigned_position_id",
    )
    # Self-referential: child positions that list this as their parent
    child_positions: Mapped[list[OptionsPosition]] = relationship(
        back_populates="parent_position",
        foreign_keys="OptionsPosition.parent_position_id",
    )
    parent_position: Mapped[OptionsPosition | None] = relationship(
        back_populates="child_positions",
        remote_side="OptionsPosition.id",
        foreign_keys="OptionsPosition.parent_position_id",
    )
