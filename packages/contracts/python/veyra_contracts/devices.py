"""Device / IoT contracts. docs/architecture/10-IOT.md, docs/security/04-DEVICE-TRUST.md"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from veyra_contracts.enums import ConnectionProtocol, DeviceTrustStatus, DeviceType


class Device(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    type: DeviceType
    trust_status: DeviceTrustStatus = DeviceTrustStatus.UNPAIRED
    last_seen_at: datetime | None = None


class DeviceCapability(BaseModel):
    device_id: str
    capability_key: str
    value_schema: dict[str, Any] = Field(default_factory=dict)


class Connection(BaseModel):
    device_id: str
    protocol: ConnectionProtocol
    address: str
    credentials_ref: str | None = Field(
        default=None,
        description="Opaque reference into the OS credential store. Never "
        "a raw secret — see docs/security/05-DATA-PROTECTION.md §1.",
    )


class DevicePermission(BaseModel):
    device_id: str
    capability_key: str
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_valid(self, at: datetime | None = None) -> bool:
        now = at or datetime.now(UTC)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True


class Command(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    device_id: str
    capability_key: str
    requested_value: Any
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result: str | None = None
