"""init backoffice tables

Revision ID: 20260421_01
Revises:
Create Date: 2026-04-21 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260421_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inariz_steam_prod",
        sa.Column("measured_at_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("steam_production_m3_h", sa.Float(), nullable=False),
        sa.Column(
            "unit",
            sa.String(),
            nullable=True,
            server_default=sa.text("'m3/h'"),
        ),
        sa.PrimaryKeyConstraint("measured_at_utc"),
    )
    op.create_table(
        "inariz_steam_forecast",
        sa.Column("measured_at_utc", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("steam_production_m3_h", sa.Float(), nullable=False),
        sa.Column(
            "unit",
            sa.String(),
            nullable=True,
            server_default=sa.text("'m3/h'"),
        ),
        sa.PrimaryKeyConstraint("measured_at_utc"),
    )
    op.create_table(
        "forecast_schedule",
        sa.Column("schedule_id", sa.String(), nullable=False),
        sa.Column("site", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("n_splits", sa.Integer(), nullable=False),
        sa.Column("gap", sa.Integer(), nullable=False),
        sa.Column("test_size", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("trigger_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("last_triggered_at", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("schedule_id"),
    )


def downgrade() -> None:
    op.drop_table("forecast_schedule")
    op.drop_table("inariz_steam_forecast")
    op.drop_table("inariz_steam_prod")
