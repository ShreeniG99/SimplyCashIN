"""initial schema (pgvector extension + all M1 tables)

Revision ID: 0001
Revises:
Create Date: 2026-06-19
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBED_DIM = 384


def _owner_fk():
    return sa.ForeignKeyConstraint(["owner_id"], ["owner.id"],
                                   deferrable=True, initially="DEFERRED")


def _buyer_fk():
    return sa.ForeignKeyConstraint(["buyer_id"], ["buyer.id"],
                                   deferrable=True, initially="DEFERRED")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "owner",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("business", sa.String(), nullable=False),
        sa.Column("max_extension_days", sa.Integer(), nullable=False),
        sa.Column("min_upfront_pct", sa.Integer(), nullable=False),
    )
    op.create_table(
        "buyer",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("relationship_years", sa.Float(), nullable=False),
        sa.Column("on_time_rate", sa.Float(), nullable=False),
        sa.Column("preferred_channel", sa.String(), nullable=False),
        _owner_fk(),
    )
    op.create_table(
        "invoice",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("buyer_id", sa.String(), nullable=False),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("days_overdue", sa.Integer(), nullable=False),
        _buyer_fk(),
    )
    op.create_table(
        "conversation_turn",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("buyer_id", sa.String(), nullable=False),
        sa.Column("sender", sa.String(), nullable=False),
        sa.Column("agent", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        _buyer_fk(),
    )
    op.create_table(
        "cash_event",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("counterparty", sa.String(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        _owner_fk(),
    )
    op.create_table(
        "escalation",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("buyer_id", sa.String(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=True),
        sa.Column("channel_kind", sa.String(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolution", sa.String(), nullable=True),
        _buyer_fk(),
    )
    op.create_table(
        "memory_record",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("buyer_id", sa.String(), nullable=False),
        sa.Column("tone", sa.String(), nullable=False),
        sa.Column("timing", sa.String(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        _buyer_fk(),
    )
    op.create_table(
        "memory_embedding",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("buyer_id", sa.String(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=False),
        _buyer_fk(),
    )


def downgrade() -> None:
    for table in ("memory_embedding", "memory_record", "escalation", "cash_event",
                  "conversation_turn", "invoice", "buyer", "owner"):
        op.drop_table(table)
