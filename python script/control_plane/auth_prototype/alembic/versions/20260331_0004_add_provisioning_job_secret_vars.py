"""add secret vars storage for provisioning jobs

Revision ID: 20260331_0004
Revises: 20260328_0003
Create Date: 2026-03-31 16:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260331_0004"
down_revision = "20260328_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("provisioning_jobs", sa.Column("secret_vars_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("provisioning_jobs", "secret_vars_json")
