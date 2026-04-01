"""SQLAlchemy ORM model for the RawTransaction entity."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import RawTransactionStatus

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.upload import Upload


class RawTransaction(Base):
    """Stores the raw CSV row data before parsing/classification."""

    __tablename__ = "raw_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    is_internal_transfer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    status: Mapped[RawTransactionStatus] = mapped_column(
        Enum(RawTransactionStatus, name="raw_transaction_status"),
        nullable=False,
        default=RawTransactionStatus.ACTIVE,
    )

    # Relationships
    upload: Mapped[Upload] = relationship(back_populates="raw_transactions")
    transaction: Mapped[Transaction | None] = relationship(back_populates="raw_transaction")
