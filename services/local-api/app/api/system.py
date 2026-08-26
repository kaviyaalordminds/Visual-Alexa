"""GET /system — backs the Phase 1 status screen (product brief §40)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.setting import SystemSetting

router = APIRouter(tags=["system"])

ComponentStatus = Literal[
    "CONNECTED", "NOT CONFIGURED", "NOT ENABLED", "NOT CONNECTED", "ACTIVE", "ERROR"
]


class SystemStatus(BaseModel):
    desktop: ComponentStatus
    local_api: ComponentStatus
    database: ComponentStatus
    ai: ComponentStatus
    voice: ComponentStatus
    vision: ComponentStatus
    computer_control: ComponentStatus
    iot: ComponentStatus
    security: ComponentStatus


@router.get("/system", response_model=SystemStatus)
async def system_status(session: AsyncSession = Depends(get_session)) -> SystemStatus:
    result = await session.execute(select(SystemSetting))
    settings_by_key = {row.key: row.value for row in result.scalars()}

    return SystemStatus(
        # The desktop shell that calls this endpoint is, by definition,
        # connected if this response is returned to it.
        desktop="CONNECTED",
        local_api="CONNECTED",
        database="CONNECTED",
        ai="CONNECTED" if settings_by_key.get("ai.configured") else "NOT CONFIGURED",
        voice="CONNECTED" if settings_by_key.get("voice.configured") else "NOT CONFIGURED",
        vision="CONNECTED" if settings_by_key.get("vision.configured") else "NOT CONFIGURED",
        computer_control=(
            "CONNECTED" if settings_by_key.get("computer_control.enabled") else "NOT ENABLED"
        ),
        iot=(
            "CONNECTED" if settings_by_key.get("external_devices.enabled") else "NOT CONNECTED"
        ),
        security="ACTIVE" if settings_by_key.get("security.active") else "ERROR",
    )
