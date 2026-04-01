"""initial_schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-03-30 00:00:00.000000

Creates the complete v0.1 schema:
  uploads, raw_transactions, transactions,
  options_positions, options_position_legs, equity_positions

Includes all required indexes from PRD §4.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all tables, enums, and indexes."""

    # ------------------------------------------------------------------
    # PostgreSQL ENUM types — use raw DDL to avoid asyncpg checkfirst bug
    # ------------------------------------------------------------------
    enum_defs = [
        ("upload_status", ["ACTIVE", "SOFT_DELETED"]),
        ("raw_transaction_status", ["ACTIVE", "DUPLICATE", "POSSIBLE_DUPLICATE", "PARSE_ERROR"]),
        ("transaction_status", ["ACTIVE", "SOFT_DELETED"]),
        ("transaction_category", [
            "OPTIONS_SELL_TO_OPEN", "OPTIONS_BUY_TO_OPEN",
            "OPTIONS_BUY_TO_CLOSE", "OPTIONS_SELL_TO_CLOSE",
            "OPTIONS_EXPIRED", "OPTIONS_ASSIGNED", "OPTIONS_EXERCISED",
            "EQUITY_BUY", "EQUITY_SELL", "DIVIDEND", "TRANSFER",
            "INTEREST", "FEE", "JOURNAL", "OTHER",
        ]),
        ("option_type", ["CALL", "PUT"]),
        ("position_direction", ["LONG", "SHORT"]),
        ("options_position_status", [
            "OPEN", "PARTIALLY_CLOSED", "CLOSED",
            "EXPIRED", "ASSIGNED", "EXERCISED",
        ]),
        ("leg_role", ["OPEN", "CLOSE"]),
        ("equity_position_source", ["PURCHASE", "ASSIGNMENT", "EXERCISE"]),
        ("equity_position_status", ["OPEN", "CLOSED"]),
    ]
    for name, values in enum_defs:
        vals = ", ".join(f"'{v}'" for v in values)
        op.execute(sa.text(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({vals}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
        ))

    # ------------------------------------------------------------------
    # 1. uploads
    # ------------------------------------------------------------------
    op.create_table(
        "uploads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("broker", sa.String(50), nullable=False, server_default="etrade"),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("options_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("possible_duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parse_error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("internal_transfer_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            postgresql.ENUM("ACTIVE", "SOFT_DELETED", name="upload_status", create_type=False),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 2. raw_transactions
    # ------------------------------------------------------------------
    op.create_table(
        "raw_transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("upload_id", sa.UUID(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_internal_transfer", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "ACTIVE",
                "DUPLICATE",
                "POSSIBLE_DUPLICATE",
                "PARSE_ERROR",
                name="raw_transaction_status",
                create_type=False,
            ),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_transactions_upload_id", "raw_transactions", ["upload_id"])

    # ------------------------------------------------------------------
    # 3. transactions
    # ------------------------------------------------------------------
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("raw_transaction_id", sa.UUID(), nullable=False),
        sa.Column("upload_id", sa.UUID(), nullable=False),
        sa.Column("broker_transaction_id", sa.String(100), nullable=True),
        sa.Column("broker_name", sa.String(50), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("option_symbol", sa.String(50), nullable=True),
        sa.Column("strike", sa.Numeric(12, 4), nullable=True),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column(
            "option_type",
            postgresql.ENUM("CALL", "PUT", name="option_type", create_type=False),
            nullable=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 5), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=True),
        sa.Column("commission", sa.Numeric(12, 4), nullable=False),
        sa.Column("amount", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(
                "OPTIONS_SELL_TO_OPEN",
                "OPTIONS_BUY_TO_OPEN",
                "OPTIONS_BUY_TO_CLOSE",
                "OPTIONS_SELL_TO_CLOSE",
                "OPTIONS_EXPIRED",
                "OPTIONS_ASSIGNED",
                "OPTIONS_EXERCISED",
                "EQUITY_BUY",
                "EQUITY_SELL",
                "DIVIDEND",
                "TRANSFER",
                "INTEREST",
                "FEE",
                "JOURNAL",
                "OTHER",
                name="transaction_category",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("ACTIVE", "SOFT_DELETED", name="transaction_status", create_type=False),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["raw_transaction_id"],
            ["raw_transactions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_raw_transaction_id", "transactions", ["raw_transaction_id"])
    op.create_index("ix_transactions_upload_id", "transactions", ["upload_id"])
    # PRD §4 required composite index
    op.create_index(
        "ix_transactions_upload_symbol_category_date",
        "transactions",
        ["upload_id", "symbol", "category", "transaction_date"],
    )

    # ------------------------------------------------------------------
    # 4. options_positions  (self-referential FK on parent_position_id)
    # ------------------------------------------------------------------
    op.create_table(
        "options_positions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("underlying", sa.String(20), nullable=False),
        sa.Column("option_symbol", sa.String(50), nullable=False),
        sa.Column("strike", sa.Numeric(12, 4), nullable=False),
        sa.Column("expiry", sa.Date(), nullable=False),
        sa.Column(
            "option_type",
            postgresql.ENUM("CALL", "PUT", name="option_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "direction",
            postgresql.ENUM("LONG", "SHORT", name="position_direction", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "OPEN",
                "PARTIALLY_CLOSED",
                "CLOSED",
                "EXPIRED",
                "ASSIGNED",
                "EXERCISED",
                name="options_position_status",
                create_type=False,
            ),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("realized_pnl", sa.Numeric(12, 4), nullable=True),
        sa.Column("is_covered_call", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("parent_position_id", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_position_id"],
            ["options_positions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_options_positions_parent_position_id",
        "options_positions",
        ["parent_position_id"],
    )
    # PRD §4 required composite index
    op.create_index(
        "ix_options_positions_underlying_status_expiry",
        "options_positions",
        ["underlying", "status", "expiry"],
    )

    # ------------------------------------------------------------------
    # 5. options_position_legs
    # ------------------------------------------------------------------
    op.create_table(
        "options_position_legs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("position_id", sa.UUID(), nullable=False),
        sa.Column("transaction_id", sa.UUID(), nullable=False),
        sa.Column(
            "leg_role",
            postgresql.ENUM("OPEN", "CLOSE", name="leg_role", create_type=False),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(15, 5), nullable=False),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["options_positions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_options_position_legs_position_id",
        "options_position_legs",
        ["position_id"],
    )
    op.create_index(
        "ix_options_position_legs_transaction_id",
        "options_position_legs",
        ["transaction_id"],
    )

    # ------------------------------------------------------------------
    # 6. equity_positions
    # ------------------------------------------------------------------
    op.create_table(
        "equity_positions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 5), nullable=False),
        sa.Column("cost_basis_per_share", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "source",
            postgresql.ENUM(
                "PURCHASE",
                "ASSIGNMENT",
                "EXERCISE",
                name="equity_position_source",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("assigned_position_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("OPEN", "CLOSED", name="equity_position_status", create_type=False),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("equity_realized_pnl", sa.Numeric(12, 4), nullable=True),
        sa.Column("close_transaction_id", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_position_id"],
            ["options_positions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["close_transaction_id"],
            ["transactions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_equity_positions_assigned_position_id",
        "equity_positions",
        ["assigned_position_id"],
    )
    op.create_index(
        "ix_equity_positions_close_transaction_id",
        "equity_positions",
        ["close_transaction_id"],
    )


def downgrade() -> None:
    """Drop all tables and enums in reverse dependency order."""

    # Tables (reverse FK order)
    op.drop_table("equity_positions")
    op.drop_table("options_position_legs")
    op.drop_table("options_positions")
    op.drop_table("transactions")
    op.drop_table("raw_transactions")
    op.drop_table("uploads")

    # ENUM types
    for enum_name in [
        "equity_position_status",
        "equity_position_source",
        "leg_role",
        "options_position_status",
        "position_direction",
        "option_type",
        "transaction_category",
        "transaction_status",
        "raw_transaction_status",
        "upload_status",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
