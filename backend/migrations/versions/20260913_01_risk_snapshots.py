"""Establish the baseline schema and add versioned risk snapshots.

Revision ID: 20260913_01
Revises: None
"""

from alembic import op
import sqlalchemy as sa

from app.database.base import Base
import app.models  # noqa: F401


revision = "20260913_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    inspector = sa.inspect(connection)
    if "customers" not in inspector.get_table_names():
        # This revision is the adoption baseline for the pre-Alembic project.
        Base.metadata.create_all(bind=connection)
        return

    columns = {column["name"] for column in inspector.get_columns("risk_scores")}
    if "risk_band" not in columns:
        op.add_column(
            "risk_scores",
            sa.Column(
                "risk_band",
                sa.String(length=32),
                nullable=False,
                server_default="unscored",
            ),
        )
    if "data_cutoff_step" not in columns:
        op.add_column(
            "risk_scores",
            sa.Column(
                "data_cutoff_step", sa.Integer(), nullable=False, server_default="0"
            ),
        )
    if "evidence" not in columns:
        op.add_column(
            "risk_scores",
            sa.Column(
                "evidence",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'::json"),
            ),
        )

    constraint_names = {
        constraint.get("name")
        for constraint in sa.inspect(connection).get_unique_constraints("risk_scores")
    }
    if "uq_risk_scores_risk_snapshot_identity" not in constraint_names:
        op.create_unique_constraint(
            "uq_risk_scores_risk_snapshot_identity",
            "risk_scores",
            ["customer_id", "data_cutoff_step", "model_version", "feature_version"],
        )
    check_names = {
        constraint.get("name")
        for constraint in sa.inspect(connection).get_check_constraints("risk_scores")
    }
    if "ck_risk_scores_risk_band_value" not in check_names:
        op.create_check_constraint(
            "ck_risk_scores_risk_band_value",
            "risk_scores",
            "risk_band IN ('low', 'medium', 'high', 'unscored')",
        )


def downgrade() -> None:
    # The baseline may have adopted an existing database, so only Phase 1 fields
    # are reversed; pre-existing application tables are never dropped here.
    connection = op.get_bind()
    if "risk_scores" not in sa.inspect(connection).get_table_names():
        return
    op.drop_constraint(
        "uq_risk_scores_risk_snapshot_identity", "risk_scores", type_="unique"
    )
    op.drop_constraint(
        "ck_risk_scores_risk_band_value", "risk_scores", type_="check"
    )
    op.drop_column("risk_scores", "evidence")
    op.drop_column("risk_scores", "data_cutoff_step")
    op.drop_column("risk_scores", "risk_band")
