from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import ConnectionProtocol, DeviceTrustStatus, DeviceType

from app.db.base import Base, IDMixin, TimestampMixin


class Device(Base, IDMixin, TimestampMixin):
    """docs/architecture/10-IOT.md, docs/security/04-DEVICE-TRUST.md —
    deny-by-default: trust_status starts UNPAIRED and must pass the full
    pair -> identify -> authenticate -> authorize flow before any
    DevicePermission can be granted."""

    __tablename__ = "devices"

    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[DeviceType] = mapped_column(Enum(DeviceType))
    trust_status: Mapped[DeviceTrustStatus] = mapped_column(
        Enum(DeviceTrustStatus), default=DeviceTrustStatus.UNPAIRED
    )
    protocol: Mapped[ConnectionProtocol | None] = mapped_column(
        Enum(ConnectionProtocol), nullable=True
    )
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credentials_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeviceCapability(Base, IDMixin, TimestampMixin):
    __tablename__ = "device_capabilities"

    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    capability_key: Mapped[str] = mapped_column(String(200))
    value_schema: Mapped[dict] = mapped_column(JSON, default=dict)


class DevicePermission(Base, IDMixin, TimestampMixin):
    __tablename__ = "device_permissions"

    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    capability_key: Mapped[str] = mapped_column(String(200))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
