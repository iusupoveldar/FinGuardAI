"""Add the idempotent investigation snapshot key.

Revision ID: 20260914_02
Revises: 20260913_01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_02"
down_revision = "20260913_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {item["name"] for item in inspector.get_columns("investigations")}
    if "snapshot_key" not in columns:
        op.add_column(
            "investigations",
            sa.Column("snapshot_key", sa.String(length=64), nullable=True),
        )
        # Legacy placeholder rows did not freeze enough state to be reusable.
        op.execute(
            "UPDATE investigations "
            "SET snapshot_key = md5('legacy:' || investigation_id::text) "
            "WHERE snapshot_key IS NULL"
        )
        op.alter_column("investigations", "snapshot_key", nullable=False)
    indexes = {
        item["name"]
        for item in sa.inspect(connection).get_indexes("investigations")
    }
    if "ix_investigations_snapshot_key" not in indexes:
        op.create_index(
            "ix_investigations_snapshot_key",
            "investigations",
            ["snapshot_key"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("ix_investigations_snapshot_key", table_name="investigations")
    op.drop_column("investigations", "snapshot_key")
