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

Subsystem activation (docs/subsystem-activation/SUBSYSTEM-ACTIVATION-
REPORT.md): `ai`/`voice`/`vision`/`computer_control`/`iot` used to be
static `system_settings` boolean-flag lookups with no relationship to
whether the subsystem was actually usable. They are now each derived from
a real check in `app/services/subsystem_health.py` — see that module's
own docstring for exactly what each one verifies. `DEGRADED` and
`DISABLED` are two new `ComponentStatus` values added here, additively
(every previously-possible value and every existing test's exact string
still holds) — this is not a change to the response *shape* the frontend
already depends on, only a richer, real set of values a field can take,
plus an additive `details` map carrying a human-readable reason per
component.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from computer_control.core.capabilities import detect_capabilities
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import EventType

from app.core.config import get_settings
from app.core.event_bus import event_bus
from app.core.readiness import uptime_seconds
from app.core.version import BACKEND_VERSION
from app.db.session import get_session
from app.models.memory import Memory as MemoryRow
from app.models.setting import SystemSetting
from app.services.browser.manager import browser_manager
from app.services.device_pairing import device_pairing_service
from app.services.subsystem_health import (
    ComponentStatus,
    SubsystemHealth,
    compute_ai_status,
    compute_browser_status,
    compute_computer_control_status,
    compute_iot_status,
    compute_vision_status,
    compute_voice_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


class SystemStatus(BaseModel):
    desktop: ComponentStatus
    local_api: ComponentStatus
    database: ComponentStatus
    ai: ComponentStatus
    voice: ComponentStatus
    vision: ComponentStatus
    computer_control: ComponentStatus
    browser: ComponentStatus
    memory: ComponentStatus
    iot: ComponentStatus
    security: ComponentStatus
    # Human-readable reason per component (e.g. "database" -> "..."),
    # populated for every field this module derives from a real check.
    # Additive and optional — a frontend that doesn't know about this
    # field simply ignores it.
    details: dict[str, str] = Field(default_factory=dict)
    # Part 48 (diagnostics: "VERSION... uptime"), Part 53 (versioning) —
    # the same single source of truth every manifest in the repo is
    # tested against (tests/unit/test_version_consistency.py).
    version: str = BACKEND_VERSION
    uptime_seconds: float | None = None


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


# Phase 13 (docs/phase-13-audit.md §1) — `EventType.SYSTEM_HEALTH_CHANGED`
# existed since Phase 1 but was never actually published anywhere,
# confirmed dead. `GET /system` is the one place the full picture is
# already computed on every call — comparing this call's result against
# the last one and publishing only the fields that actually changed is a
# real, cheap way to make that event real without a second, parallel
# health-polling loop. Process-global like every other "last known state"
# registry in this codebase (`subsystem_health.py`'s own AI-check cache).
_last_status_snapshot: dict[str, str] | None = None

# The component fields worth diffing — excludes `details`/`version`/
# `uptime_seconds`, which change on every single call (uptime) or carry
# free-text reasons that would make near-every poll "changed."
_DIFFABLE_FIELDS = (
    "desktop",
    "local_api",
    "database",
    "ai",
    "voice",
    "vision",
    "computer_control",
    "browser",
    "memory",
    "iot",
    "security",
)


def reset_last_status_snapshot() -> None:
    """Test-isolation helper — process-global like every other registry
    here, so one test's health snapshot must not suppress the next
    test's first real SYSTEM_HEALTH_CHANGED event."""
    global _last_status_snapshot
    _last_status_snapshot = None


async def _compute_memory_status(session: AsyncSession, *, database_live: bool) -> SubsystemHealth:
    """PHASE_12_AUDIT.md §3 — `memory` had no field in `/system` at all.
    A real query against the actual `memories` table (not just the
    generic `SELECT 1` liveness ping above), so a memory-table-specific
    problem (e.g. schema drift on just this table) is distinguishable
    from an outright database outage."""
    if not database_live:
        return SubsystemHealth(
            status="ERROR", reason="Memory is unavailable because the database is not live."
        )
    try:
        await session.execute(select(MemoryRow.id).limit(1))
    except Exception:
        logger.exception("[VEYRA] /system: memory table check failed")
        return SubsystemHealth(status="ERROR", reason="The memory table could not be queried.")
    return SubsystemHealth(status="CONNECTED", reason="Memory table is live and queryable.")


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

    settings = get_settings()
    ai_health = compute_ai_status(settings)
    voice_health = compute_voice_status(settings)
    vision_health = compute_vision_status(settings)
    computer_control_health = compute_computer_control_status(
        enabled_flag=bool(settings_by_key.get("computer_control.enabled")),
        capabilities=detect_capabilities(),
    )
    browser_health = compute_browser_status(browser_manager)
    memory_health = await _compute_memory_status(session, database_live=database_live)
    iot_health = compute_iot_status(device_pairing_service)
    security_active = bool(settings_by_key.get("security.active"))

    status = SystemStatus(
        # The desktop shell that calls this endpoint is, by definition,
        # connected if this response is returned to it — same for the
        # Local API process itself (it is the one constructing this
        # response). Neither claim can be false while this code runs.
        desktop="CONNECTED",
        local_api="CONNECTED",
        database="CONNECTED" if database_live else "ERROR",
        ai=ai_health.status,
        voice=voice_health.status,
        vision=vision_health.status,
        computer_control=computer_control_health.status,
        browser=browser_health.status,
        memory=memory_health.status,
        iot=iot_health.status,
        security="ACTIVE" if security_active else "ERROR",
        details={
            "ai": ai_health.reason,
            "voice": voice_health.reason,
            "vision": vision_health.reason,
            "computer_control": computer_control_health.reason,
            "browser": browser_health.reason,
            "memory": memory_health.reason,
            "iot": iot_health.reason,
        },
        uptime_seconds=uptime_seconds(),
    )
    await _publish_health_change_if_any(status)
    return status


async def _publish_health_change_if_any(status: SystemStatus) -> None:
    global _last_status_snapshot
    snapshot = {field: getattr(status, field) for field in _DIFFABLE_FIELDS}
    if _last_status_snapshot is not None:
        changed = {
            field: {"from": _last_status_snapshot[field], "to": value}
            for field, value in snapshot.items()
            if _last_status_snapshot[field] != value
        }
        if changed:
            await event_bus.publish_type(
                EventType.SYSTEM_HEALTH_CHANGED, str(uuid4()), {"changed": changed}
            )
    _last_status_snapshot = snapshot
