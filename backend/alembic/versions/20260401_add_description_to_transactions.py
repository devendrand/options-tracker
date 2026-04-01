"""add_description_to_transactions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-01 00:00:00.000000

Adds the nullable ``description`` column to the ``transactions`` table.
This field is required for the Tier 2 composite deduplication key (F-08),
which includes the raw CSV description alongside trade_date, symbol,
quantity, and amount among its 10 fields.

Also adds a partial index on the four highest-cardinality dedup key fields
(trade_date, symbol, quantity, amount) scoped to non-soft-deleted rows.
This index supports the fast partial-match (POSSIBLE_DUPLICATE) lookup
path without indexing rows that are already logically removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add description column and partial dedup index to transactions."""
    # Add the nullable description column after action.
    # No NOT NULL constraint — existing rows naturally have NULL here and no
    # server_default is needed because this is an optional field.
    op.add_column(
        "transactions",
        sa.Column("description", sa.String(500), nullable=True),
    )

    # Partial index for the deduplication fast-path lookup.
    # Covers the four lowest-unique-count fields of the 10-field composite key:
    # trade_date + symbol + quantity + amount.
    # The WHERE clause excludes SOFT_DELETED rows so the index stays lean and
    # the planner only scans rows that can actually match an incoming duplicate.
    op.create_index(
        "ix_transactions_dedup_partial",
        "transactions",
        ["trade_date", "symbol", "quantity", "amount"],
        postgresql_where=sa.text("status != 'SOFT_DELETED'"),
    )


def downgrade() -> None:
    """Remove description column and partial dedup index from transactions."""
    op.drop_index("ix_transactions_dedup_partial", table_name="transactions")
    op.drop_column("transactions", "description")
