"""GET /devices. docs/security/04-DEVICE-TRUST.md — deny-by-default; no
pairing flow is implemented in Phase 1 (no protocol adapters exist), so
this list is always empty until a future phase adds a real adapter.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import DeviceTrustStatus, DeviceType

from app.db.session import get_session
from app.models.device import Device as DeviceRow

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceOut(BaseModel):
    id: str
    name: str
    type: DeviceType
    trust_status: DeviceTrustStatus
    last_seen_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[DeviceOut])
async def list_devices(session: AsyncSession = Depends(get_session)) -> list[DeviceOut]:
    result = await session.execute(select(DeviceRow))
    return [DeviceOut.model_validate(row) for row in result.scalars()]
