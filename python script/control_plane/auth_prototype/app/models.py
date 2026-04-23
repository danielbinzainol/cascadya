from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class TimestampedMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampedMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keycloak_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    preferred_username: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )


class Role(TimestampedMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", server_default="", nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary=user_roles,
        back_populates="roles",
        lazy="selectin",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )


class Permission(TimestampedMixin, Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="", server_default="", nullable=False)

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions,
        back_populates="permissions",
        lazy="selectin",
    )


class Site(TimestampedMixin, Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), default="", server_default="", nullable=False)
    country: Mapped[str] = mapped_column(String(64), default="FR", server_default="FR", nullable=False)
    city: Mapped[str] = mapped_column(String(120), default="", server_default="", nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Europe/Paris",
        server_default="Europe/Paris",
        nullable=False,
    )
    address_line1: Mapped[str] = mapped_column(String(255), default="", server_default="", nullable=False)
    notes: Mapped[str] = mapped_column(String(1000), default="", server_default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())

    assets: Mapped[list["InventoryAsset"]] = relationship(
        back_populates="site",
        lazy="selectin",
    )
    scans: Mapped[list["InventoryScan"]] = relationship(
        back_populates="site",
        lazy="selectin",
    )
    provisioning_jobs: Mapped[list["ProvisioningJob"]] = relationship(
        back_populates="site",
        lazy="selectin",
    )


class InventoryScan(TimestampedMixin, Base):
    __tablename__ = "inventory_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="requested", server_default="requested", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual", server_default="manual", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="scan", server_default="scan", nullable=False)
    target_label: Mapped[str] = mapped_column(String(255), default="", server_default="", nullable=False)
    target_ip: Mapped[str] = mapped_column(String(64), default="", server_default="", nullable=False)
    teltonika_router_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    site: Mapped[Site | None] = relationship(back_populates="scans", lazy="selectin")
    requested_by_user: Mapped[User | None] = relationship(lazy="selectin")
    discovered_assets: Mapped[list["InventoryAsset"]] = relationship(
        back_populates="discovered_by_scan",
        lazy="selectin",
    )


class InventoryAsset(TimestampedMixin, Base):
    __tablename__ = "inventory_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    discovered_by_scan_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_scans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asset_type: Mapped[str] = mapped_column(String(64), default="industrial_pc", server_default="industrial_pc", nullable=False)
    registration_status: Mapped[str] = mapped_column(
        String(32),
        default="discovered",
        server_default="discovered",
        nullable=False,
        index=True,
    )
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inventory_hostname: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    naming_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    management_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    teltonika_router_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown", server_default="unknown", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="scan", server_default="scan", nullable=False)
    management_interface: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uplink_interface: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wireguard_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(String(1000), default="", server_default="", nullable=False)
    provisioning_vars: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    site: Mapped[Site | None] = relationship(back_populates="assets", lazy="selectin")
    discovered_by_scan: Mapped[InventoryScan | None] = relationship(back_populates="discovered_assets", lazy="selectin")
    provisioning_jobs: Mapped[list["ProvisioningJob"]] = relationship(
        back_populates="asset",
        lazy="selectin",
    )


class ProvisioningJob(TimestampedMixin, Base):
    __tablename__ = "provisioning_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="prepared", server_default="prepared", nullable=False, index=True)
    execution_mode: Mapped[str] = mapped_column(String(32), default="mock", server_default="mock", nullable=False)
    playbook_name: Mapped[str] = mapped_column(String(255), nullable=False)
    inventory_group: Mapped[str] = mapped_column(String(120), default="cascadya_ipc", server_default="cascadya_ipc", nullable=False)
    command_preview: Mapped[str] = mapped_column(String(2000), default="", server_default="", nullable=False)
    context_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    secret_vars_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    logs_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    site: Mapped[Site | None] = relationship(back_populates="provisioning_jobs", lazy="selectin")
    asset: Mapped[InventoryAsset | None] = relationship(back_populates="provisioning_jobs", lazy="selectin")
    requested_by_user: Mapped[User | None] = relationship(lazy="selectin")
