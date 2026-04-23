"""extend users for oidc and management

Revision ID: 20260327_0002
Revises: 20260327_0001
Create Date: 2026-03-27 14:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260327_0002"
down_revision = "20260327_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_username", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_users_preferred_username"), "users", ["preferred_username"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_preferred_username"), table_name="users")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "preferred_username")
