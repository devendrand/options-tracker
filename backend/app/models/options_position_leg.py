"""SQLAlchemy ORM model for the OptionsPositionLeg join entity."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LegRole

if TYPE_CHECKING:
    from app.models.options_position import OptionsPosition
    from app.models.transaction import Transaction


class OptionsPositionLeg(Base):
    """Join table linking transactions to options positions as open/close legs.

    Supports multiple open legs (scale-in) and multiple close legs (partial close)
    per position by using a join table rather than single FK columns.
    """

    __tablename__ = "options_position_legs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("options_positions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leg_role: Mapped[LegRole] = mapped_column(
        Enum(LegRole, name="leg_role"),
        nullable=False,
    )
    # Positive quantity for this specific leg (supports partial/scale-in)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 5), nullable=False)

    # Relationships
    position: Mapped[OptionsPosition] = relationship(back_populates="legs")
    transaction: Mapped[Transaction] = relationship(back_populates="position_legs")
