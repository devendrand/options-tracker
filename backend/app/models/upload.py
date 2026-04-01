"""SQLAlchemy ORM model for the Upload entity."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import UploadStatus

if TYPE_CHECKING:
    from app.models.raw_transaction import RawTransaction
    from app.models.transaction import Transaction


class Upload(Base):
    """Represents a single CSV file upload from a user."""

    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    broker: Mapped[str] = mapped_column(String(50), nullable=False, default="etrade")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    options_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    possible_duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parse_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    internal_transfer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status"),
        nullable=False,
        default=UploadStatus.ACTIVE,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationships
    raw_transactions: Mapped[list[RawTransaction]] = relationship(
        back_populates="upload",
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="upload",
    )
