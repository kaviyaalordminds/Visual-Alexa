"""GET /system — backs the Phase 1 status screen (product brief §40).

Phase 9 audit finding (docs/PHASE-9-AUDIT.md P1-2): `database` used to be a
bare literal, true only by accident of the settings query above it having
already succeeded — a future refactor could move/remove that query and
silently turn the claim into a lie. `_database_is_live()` below is now the
one explicit, named check this field is derived from, and the whole
response degrades to reporting the failure instead of crashing (a 500 here
told the caller nothing about *which* component was the problem; the
brief is explicit that a status endpoint must never merely disappear when
the thing it's reporting on is unhealthy).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.setting import SystemSetting

logger = logging.getLogger(__name__)

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


async def _database_is_live(session: AsyncSession) -> bool:
    """The one real, independent liveness check `database` is derived
    from — a trivial round-trip query, deliberately not reused from any
    other handler logic so this claim can never become true by accident."""
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("[VEYRA] /system: database liveness check failed")
        return False


@router.get("/system", response_model=SystemStatus)
async def system_status(session: AsyncSession = Depends(get_session)) -> SystemStatus:
    database_live = await _database_is_live(session)

    settings_by_key: dict[str, object] = {}
    if database_live:
        try:
            result = await session.execute(select(SystemSetting))
            settings_by_key = {row.key: row.value for row in result.scalars()}
        except Exception:
            # The liveness ping above succeeded but this query still
            # failed (e.g. schema drift) — report it truthfully rather
            # than crashing the whole status endpoint.
            logger.exception("[VEYRA] /system: settings query failed")
            database_live = False

    return SystemStatus(
        # The desktop shell that calls this endpoint is, by definition,
        # connected if this response is returned to it — same for the
        # Local API process itself (it is the one constructing this
        # response). Neither claim can be false while this code runs.
        desktop="CONNECTED",
        local_api="CONNECTED",
        database="CONNECTED" if database_live else "ERROR",
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
