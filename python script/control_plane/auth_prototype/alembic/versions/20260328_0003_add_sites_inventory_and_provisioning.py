"""add sites, inventory, scans and provisioning jobs

Revision ID: 20260328_0003
Revises: 20260327_0002
Create Date: 2026-03-28 10:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0003"
down_revision = "20260327_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("customer_name", sa.String(length=255), server_default="", nullable=False),
        sa.Column("country", sa.String(length=64), server_default="FR", nullable=False),
        sa.Column("city", sa.String(length=120), server_default="", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Europe/Paris", nullable=False),
        sa.Column("address_line1", sa.String(length=255), server_default="", nullable=False),
        sa.Column("notes", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sites")),
    )
    op.create_index(op.f("ix_sites_code"), "sites", ["code"], unique=True)

    op.create_table(
        "inventory_scans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="requested", nullable=False),
        sa.Column("trigger_type", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("source", sa.String(length=32), server_default="scan", nullable=False),
        sa.Column("target_label", sa.String(length=255), server_default="", nullable=False),
        sa.Column("target_ip", sa.String(length=64), server_default="", nullable=False),
        sa.Column("teltonika_router_ip", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], name=op.f("fk_inventory_scans_requested_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name=op.f("fk_inventory_scans_site_id_sites"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_scans")),
    )
    op.create_index(op.f("ix_inventory_scans_requested_by_user_id"), "inventory_scans", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_inventory_scans_site_id"), "inventory_scans", ["site_id"], unique=False)

    op.create_table(
        "inventory_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("discovered_by_scan_id", sa.Integer(), nullable=True),
        sa.Column("asset_type", sa.String(length=64), server_default="industrial_pc", nullable=False),
        sa.Column("registration_status", sa.String(length=32), server_default="discovered", nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("inventory_hostname", sa.String(length=255), nullable=True),
        sa.Column("naming_slug", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("management_ip", sa.String(length=64), nullable=True),
        sa.Column("teltonika_router_ip", sa.String(length=64), nullable=True),
        sa.Column("mac_address", sa.String(length=64), nullable=True),
        sa.Column("serial_number", sa.String(length=128), nullable=True),
        sa.Column("vendor", sa.String(length=120), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("firmware_version", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("source", sa.String(length=32), server_default="scan", nullable=False),
        sa.Column("management_interface", sa.String(length=64), nullable=True),
        sa.Column("uplink_interface", sa.String(length=64), nullable=True),
        sa.Column("gateway_ip", sa.String(length=64), nullable=True),
        sa.Column("wireguard_address", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("provisioning_vars", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["discovered_by_scan_id"], ["inventory_scans.id"], name=op.f("fk_inventory_assets_discovered_by_scan_id_inventory_scans"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name=op.f("fk_inventory_assets_site_id_sites"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_assets")),
    )
    op.create_index(op.f("ix_inventory_assets_discovered_by_scan_id"), "inventory_assets", ["discovered_by_scan_id"], unique=False)
    op.create_index(op.f("ix_inventory_assets_inventory_hostname"), "inventory_assets", ["inventory_hostname"], unique=False)
    op.create_index(op.f("ix_inventory_assets_ip_address"), "inventory_assets", ["ip_address"], unique=False)
    op.create_index(op.f("ix_inventory_assets_mac_address"), "inventory_assets", ["mac_address"], unique=False)
    op.create_index(op.f("ix_inventory_assets_management_ip"), "inventory_assets", ["management_ip"], unique=False)
    op.create_index(op.f("ix_inventory_assets_registration_status"), "inventory_assets", ["registration_status"], unique=False)
    op.create_index(op.f("ix_inventory_assets_site_id"), "inventory_assets", ["site_id"], unique=False)

    op.create_table(
        "provisioning_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("asset_id", sa.Integer(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="prepared", nullable=False),
        sa.Column("execution_mode", sa.String(length=32), server_default="mock", nullable=False),
        sa.Column("playbook_name", sa.String(length=255), nullable=False),
        sa.Column("inventory_group", sa.String(length=120), server_default="cascadya_ipc", nullable=False),
        sa.Column("command_preview", sa.String(length=2000), server_default="", nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("logs_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["inventory_assets.id"], name=op.f("fk_provisioning_jobs_asset_id_inventory_assets"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], name=op.f("fk_provisioning_jobs_requested_by_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], name=op.f("fk_provisioning_jobs_site_id_sites"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provisioning_jobs")),
    )
    op.create_index(op.f("ix_provisioning_jobs_asset_id"), "provisioning_jobs", ["asset_id"], unique=False)
    op.create_index(op.f("ix_provisioning_jobs_requested_by_user_id"), "provisioning_jobs", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_provisioning_jobs_site_id"), "provisioning_jobs", ["site_id"], unique=False)
    op.create_index(op.f("ix_provisioning_jobs_status"), "provisioning_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_provisioning_jobs_status"), table_name="provisioning_jobs")
    op.drop_index(op.f("ix_provisioning_jobs_site_id"), table_name="provisioning_jobs")
    op.drop_index(op.f("ix_provisioning_jobs_requested_by_user_id"), table_name="provisioning_jobs")
    op.drop_index(op.f("ix_provisioning_jobs_asset_id"), table_name="provisioning_jobs")
    op.drop_table("provisioning_jobs")

    op.drop_index(op.f("ix_inventory_assets_site_id"), table_name="inventory_assets")
    op.drop_index(op.f("ix_inventory_assets_registration_status"), table_name="inventory_assets")
    op.drop_index(op.f("ix_inventory_assets_management_ip"), table_name="inventory_assets")
    op.drop_index(op.f("ix_inventory_assets_mac_address"), table_name="inventory_assets")
    op.drop_index(op.f("ix_inventory_assets_ip_address"), table_name="inventory_assets")
    op.drop_index(op.f("ix_inventory_assets_inventory_hostname"), table_name="inventory_assets")
    op.drop_index(op.f("ix_inventory_assets_discovered_by_scan_id"), table_name="inventory_assets")
    op.drop_table("inventory_assets")

    op.drop_index(op.f("ix_inventory_scans_site_id"), table_name="inventory_scans")
    op.drop_index(op.f("ix_inventory_scans_requested_by_user_id"), table_name="inventory_scans")
    op.drop_table("inventory_scans")

    op.drop_index(op.f("ix_sites_code"), table_name="sites")
    op.drop_table("sites")
