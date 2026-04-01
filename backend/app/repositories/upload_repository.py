"""Repository for Upload CRUD operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionStatus, UploadStatus
from app.models.transaction import Transaction
from app.models.upload import Upload


class UploadRepository:
    """Data-access layer for Upload records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def create(self, upload: Upload) -> Upload:
        """Persist a new Upload record and return it."""
        self._session.add(upload)
        await self._session.flush()
        await self._session.refresh(upload)
        return upload

    async def get_by_id(self, upload_id: uuid.UUID) -> Upload | None:
        """Return an active Upload by id, or None."""
        q = select(Upload).where(Upload.id == upload_id).where(Upload.status == UploadStatus.ACTIVE)
        result = await self._session.execute(q)
        return result.scalar_one_or_none()

    async def list_uploads(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[int, list[Upload]]:
        """Return (total_count, page) of active uploads."""
        base_q = select(Upload).where(Upload.status == UploadStatus.ACTIVE)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        rows_q = base_q.order_by(Upload.uploaded_at.desc(), Upload.id).offset(offset).limit(limit)
        rows = list((await self._session.execute(rows_q)).scalars().all())
        return total, rows

    async def soft_delete(self, upload_id: uuid.UUID) -> Upload | None:
        """Soft-delete an upload and cascade to its transactions.

        Returns the updated Upload or None if not found.
        """
        upload = await self.get_by_id(upload_id)
        if upload is None:
            return None

        now = datetime.now(UTC)
        upload.status = UploadStatus.SOFT_DELETED
        upload.deleted_at = now

        # Cascade: soft-delete all transactions from this upload
        txn_q = select(Transaction).where(
            Transaction.upload_id == upload_id,
            Transaction.status == TransactionStatus.ACTIVE,
        )
        result = await self._session.execute(txn_q)
        for txn in result.scalars().all():
            txn.status = TransactionStatus.SOFT_DELETED
            txn.deleted_at = now

        await self._session.flush()
        await self._session.refresh(upload)
        return upload

    async def get_transaction_count(self, upload_id: uuid.UUID) -> int:
        """Return count of active transactions for a given upload."""
        q = select(func.count()).where(
            Transaction.upload_id == upload_id,
            Transaction.status == TransactionStatus.ACTIVE,
        )
        result = await self._session.execute(q)
        return result.scalar_one()
