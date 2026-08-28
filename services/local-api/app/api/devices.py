"""GET /devices, POST /devices/pair + the six-stage pairing flow.
docs/security/04-DEVICE-TRUST.md, docs/phase-7/DEVICE-PAIRING.md.

CLAUDE.md: 'No device is controllable without completing PAIR ->
IDENTIFY -> AUTHENTICATE -> AUTHORIZE -> REGISTER CAPABILITIES ->
CONTROL, in order, with no stage skippable.' Every route here maps 1:1
onto one `DevicePairingService` method, which is what actually enforces
that order — these routes are a thin HTTP wrapper, not a second place
the rule could be bypassed from.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import (
    ConnectionProtocol,
    DevicePairingStage,
    DeviceTrustStatus,
    DeviceType,
    EventType,
)

from app.core.event_bus import event_bus
from app.db.session import get_session
from app.models.device import Device as DeviceRow
from app.services.device_pairing import (
    PairingStageError,
    UnknownDeviceError,
    UnregisteredCapabilityError,
    device_pairing_service,
)

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceOut(BaseModel):
    id: str
    name: str
    type: DeviceType
    trust_status: DeviceTrustStatus
    pairing_stage: DevicePairingStage | None
    last_seen_at: datetime | None

    model_config = {"from_attributes": True}


class PairRequest(BaseModel):
    name: str
    type: DeviceType
    protocol: ConnectionProtocol
    address: str | None = None


class AuthenticateRequest(BaseModel):
    secret: str


class RegisterCapabilitiesRequest(BaseModel):
    capability_keys: list[str]


class GrantPermissionRequest(BaseModel):
    capability_key: str
    ttl_seconds: int | None = None


class RevokePermissionRequest(BaseModel):
    capability_key: str


def _handle_pairing_error(exc: Exception) -> HTTPException:
    if isinstance(exc, UnknownDeviceError):
        return HTTPException(status_code=404, detail=f"Unknown device '{exc}'.")
    if isinstance(exc, (PairingStageError, UnregisteredCapabilityError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))  # pragma: no cover - defensive


@router.get("", response_model=list[DeviceOut])
async def list_devices(session: AsyncSession = Depends(get_session)) -> list[DeviceOut]:
    result = await session.execute(select(DeviceRow))
    return [DeviceOut.model_validate(row) for row in result.scalars()]


@router.post("/pair", response_model=DeviceOut, status_code=201)
async def pair_device(
    body: PairRequest, session: AsyncSession = Depends(get_session)
) -> DeviceOut:
    row = await device_pairing_service.pair(
        session, name=body.name, device_type=body.type, protocol=body.protocol, address=body.address
    )
    return DeviceOut.model_validate(row)


@router.post("/{device_id}/identify", response_model=DeviceOut)
async def identify_device(
    device_id: str, session: AsyncSession = Depends(get_session)
) -> DeviceOut:
    try:
        row = await device_pairing_service.identify(session, device_id)
    except (UnknownDeviceError, PairingStageError) as exc:
        raise _handle_pairing_error(exc) from exc
    return DeviceOut.model_validate(row)


@router.post("/{device_id}/authenticate", response_model=DeviceOut)
async def authenticate_device(
    device_id: str, body: AuthenticateRequest, session: AsyncSession = Depends(get_session)
) -> DeviceOut:
    try:
        row = await device_pairing_service.authenticate(session, device_id, secret=body.secret)
    except (UnknownDeviceError, PairingStageError) as exc:
        raise _handle_pairing_error(exc) from exc
    return DeviceOut.model_validate(row)


@router.post("/{device_id}/authorize", response_model=DeviceOut)
async def authorize_device(
    device_id: str, session: AsyncSession = Depends(get_session)
) -> DeviceOut:
    try:
        row = await device_pairing_service.authorize(session, device_id)
    except (UnknownDeviceError, PairingStageError) as exc:
        raise _handle_pairing_error(exc) from exc
    return DeviceOut.model_validate(row)


@router.post("/{device_id}/register-capabilities", response_model=DeviceOut)
async def register_capabilities(
    device_id: str, body: RegisterCapabilitiesRequest, session: AsyncSession = Depends(get_session)
) -> DeviceOut:
    try:
        row = await device_pairing_service.register_capabilities(
            session, device_id, capability_keys=body.capability_keys
        )
    except (UnknownDeviceError, PairingStageError) as exc:
        raise _handle_pairing_error(exc) from exc
    # Phase 12 — this is the real moment a device becomes controllable
    # (trust_status -> PAIRED, the last of the six mandatory pairing
    # stages before CONTROL): the honest point to call it "connected,"
    # not merely "pairing was requested." No task/tool call is in
    # progress here, so a fresh correlation_id is minted for this event,
    # matching how /tasks mints one for a new task.
    await event_bus.publish_type(
        EventType.IOT_DEVICE_CONNECTED, str(uuid4()), {"device_id": device_id}
    )
    return DeviceOut.model_validate(row)


@router.post("/{device_id}/permissions/grant", status_code=201)
async def grant_permission(
    device_id: str, body: GrantPermissionRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        permission = await device_pairing_service.grant_permission(
            session, device_id, capability_key=body.capability_key, ttl_seconds=body.ttl_seconds
        )
    except (UnknownDeviceError, PairingStageError, UnregisteredCapabilityError) as exc:
        raise _handle_pairing_error(exc) from exc
    return {
        "id": permission.id,
        "device_id": permission.device_id,
        "capability_key": permission.capability_key,
        "granted_at": permission.granted_at,
        "expires_at": permission.expires_at,
    }


@router.post("/{device_id}/permissions/revoke")
async def revoke_permission(
    device_id: str, body: RevokePermissionRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    await device_pairing_service.revoke_permission(
        session, device_id, capability_key=body.capability_key
    )
    # Phase 12 — revoking a device's only real access grant is the
    # closest real analogue this codebase has to "disconnect": there is
    # no separate unpair/forget-device operation to hook instead.
    await event_bus.publish_type(
        EventType.IOT_DEVICE_DISCONNECTED,
        str(uuid4()),
        {"device_id": device_id, "capability_key": body.capability_key},
    )
    return {"device_id": device_id, "capability_key": body.capability_key, "revoked": True}
