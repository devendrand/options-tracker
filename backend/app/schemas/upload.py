"""Pydantic schemas for the Upload API layer."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import UploadStatus


class UploadResponse(BaseModel):
    """Schema returned by upload list / create endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    broker: str
    uploaded_at: datetime
    row_count: int
    options_count: int
    duplicate_count: int
    possible_duplicate_count: int
    parse_error_count: int
    internal_transfer_count: int
    status: UploadStatus


class UploadDetailResponse(UploadResponse):
    """Upload with transaction-level stats (for detail endpoint)."""

    transaction_count: int = 0


class UploadListResponse(BaseModel):
    """Paginated list of uploads."""

    total: int
    offset: int
    limit: int
    items: list[UploadResponse]


class UploadDeleteResponse(BaseModel):
    """Response after soft-deleting an upload."""

    id: uuid.UUID
    status: UploadStatus
    warning: str | None = None
