"""memory_embedding.owner_id + RLS policies (per-owner tenancy)

The app role owns these tables, so RLS here is defense-in-depth for hosted
roles (Supabase) — request-path isolation is enforced by owner filters in the
repositories and the JWT owner dependency. Policies key on
current_setting('app.owner_id') for future non-owner connection roles.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_RLS_TABLES = ("buyer", "cash_event", "ingestion_job", "memory_embedding")


def upgrade() -> None:
    op.add_column("memory_embedding", sa.Column("owner_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_memory_embedding_owner", "memory_embedding", "owner",
        ["owner_id"], ["id"], deferrable=True, initially="DEFERRED")
    op.execute(
        "UPDATE memory_embedding SET owner_id = buyer.owner_id "
        "FROM buyer WHERE memory_embedding.buyer_id = buyer.id")

    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_owner_isolation ON {table} "
            f"USING (owner_id = current_setting('app.owner_id', true))")


def downgrade() -> None:
    for table in _RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_constraint("fk_memory_embedding_owner", "memory_embedding", type_="foreignkey")
    op.drop_column("memory_embedding", "owner_id")
