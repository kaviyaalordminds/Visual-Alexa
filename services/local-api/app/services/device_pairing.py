"""DevicePairingService — docs/phase-7/DEVICE-PAIRING.md.

CLAUDE.md: "No device is controllable without completing PAIR ->
IDENTIFY -> AUTHENTICATE -> AUTHORIZE -> REGISTER CAPABILITIES ->
CONTROL, in order, with no stage skippable." `Device.pairing_stage`
(new, Phase 7) is the strictly-ordered progress marker this service
enforces procedurally — `Device.trust_status` still only reflects the
coarser, externally-meaningful state (UNPAIRED/PAIRING/PAIRED/REVOKED).

Runtime device-permission validity (whether a specific `capability_key`
on a specific device is currently grantable) is kept in an in-memory
cache here, mirroring `orchestrator.py`'s own `_cancellation_events`/
`_pause_events` pattern: `ToolExecutor.execute()` never receives a DB
session (see `app/services/tool_registry.py`), so a device-control tool
executor cannot query `DevicePermission` rows directly at call time —
this cache is what it checks instead, kept in sync with the real DB rows
by `grant_permission`/`revoke_permission`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import ConnectionProtocol, DevicePairingStage, DeviceTrustStatus, DeviceType

from app.models.device import Device as DeviceRow
from app.models.device import DeviceCapability as DeviceCapabilityRow
from app.models.device import DevicePermission as DevicePermissionRow
from app.services.credential_manager import CredentialManager, credential_manager

_STAGE_ORDER = [
    DevicePairingStage.PAIR,
    DevicePairingStage.IDENTIFY,
    DevicePairingStage.AUTHENTICATE,
    DevicePairingStage.AUTHORIZE,
    DevicePairingStage.REGISTER_CAPABILITIES,
    DevicePairingStage.CONTROL,
]


def _stage_index(stage: DevicePairingStage | None) -> int:
    return -1 if stage is None else _STAGE_ORDER.index(stage)


def _now() -> datetime:
    return datetime.now(UTC)


class PairingStageError(ValueError):
    """A caller tried to skip a stage — CLAUDE.md: 'no stage skippable.'"""


class UnknownDeviceError(LookupError):
    pass


class UnregisteredCapabilityError(ValueError):
    """Granting control of a capability the device was never actually
    said to support (via `register_capabilities`) is refused — a
    DevicePermission must never authorize something REGISTER_CAPABILITIES
    didn't establish exists."""


class DevicePairingService:
    def __init__(self, credential_manager: CredentialManager) -> None:
        self._credential_manager = credential_manager
        # (device_id, capability_key) -> expires_at (None = no expiry).
        # Absent = no valid permission. This is the ONLY thing a device
        # control tool executor consults at call time.
        self._permission_cache: dict[tuple[str, str], datetime | None] = {}

    async def _get(self, session: AsyncSession, device_id: str) -> DeviceRow:
        result = await session.execute(select(DeviceRow).where(DeviceRow.id == device_id))
        row = result.scalars().first()
        if row is None:
            raise UnknownDeviceError(device_id)
        return row

    def _require_exact_previous(self, row: DeviceRow, expected: DevicePairingStage) -> None:
        if row.pairing_stage != expected:
            current = row.pairing_stage.value if row.pairing_stage else "not started"
            raise PairingStageError(
                f"Device is at stage '{current}' — cannot advance without "
                f"first completing '{expected.value}'."
            )

    def _require_at_least(self, row: DeviceRow, minimum: DevicePairingStage) -> None:
        if _stage_index(row.pairing_stage) < _stage_index(minimum):
            current = row.pairing_stage.value if row.pairing_stage else "not started"
            raise PairingStageError(
                f"Device is at stage '{current}' — must reach at least "
                f"'{minimum.value}' first."
            )

    # --- Stage 1: PAIR ---
    async def pair(
        self,
        session: AsyncSession,
        *,
        name: str,
        device_type: DeviceType,
        protocol: ConnectionProtocol,
        address: str | None = None,
    ) -> DeviceRow:
        row = DeviceRow(
            name=name,
            type=device_type,
            protocol=protocol,
            address=address,
            trust_status=DeviceTrustStatus.UNPAIRED,
            pairing_stage=DevicePairingStage.PAIR,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row

    # --- Stage 2: IDENTIFY ---
    async def identify(self, session: AsyncSession, device_id: str) -> DeviceRow:
        row = await self._get(session, device_id)
        self._require_exact_previous(row, DevicePairingStage.PAIR)
        row.pairing_stage = DevicePairingStage.IDENTIFY
        row.trust_status = DeviceTrustStatus.PAIRING
        row.last_seen_at = _now()
        await session.commit()
        return row

    # --- Stage 3: AUTHENTICATE ---
    async def authenticate(
        self, session: AsyncSession, device_id: str, *, secret: str
    ) -> DeviceRow:
        row = await self._get(session, device_id)
        self._require_exact_previous(row, DevicePairingStage.IDENTIFY)
        if row.credentials_ref:
            self._credential_manager.delete_credential(row.credentials_ref)
        row.credentials_ref = self._credential_manager.store_credential(secret)
        row.pairing_stage = DevicePairingStage.AUTHENTICATE
        await session.commit()
        return row

    # --- Stage 4: AUTHORIZE ---
    async def authorize(self, session: AsyncSession, device_id: str) -> DeviceRow:
        row = await self._get(session, device_id)
        self._require_exact_previous(row, DevicePairingStage.AUTHENTICATE)
        row.pairing_stage = DevicePairingStage.AUTHORIZE
        await session.commit()
        return row

    # --- Stage 5: REGISTER CAPABILITIES ---
    async def register_capabilities(
        self, session: AsyncSession, device_id: str, *, capability_keys: list[str]
    ) -> DeviceRow:
        row = await self._get(session, device_id)
        self._require_exact_previous(row, DevicePairingStage.AUTHORIZE)
        for key in capability_keys:
            session.add(DeviceCapabilityRow(device_id=row.id, capability_key=key))
        row.pairing_stage = DevicePairingStage.REGISTER_CAPABILITIES
        row.trust_status = DeviceTrustStatus.PAIRED
        await session.commit()
        return row

    # --- Stage 6: CONTROL (grant/revoke a specific capability) ---
    async def grant_permission(
        self,
        session: AsyncSession,
        device_id: str,
        *,
        capability_key: str,
        ttl_seconds: int | None = None,
    ) -> DevicePermissionRow:
        row = await self._get(session, device_id)
        # CONTROL, once reached, stays reachable — granting a second
        # capability must not have to "re-pair." Never grantable before
        # REGISTER_CAPABILITIES, though (no stage skippable).
        self._require_at_least(row, DevicePairingStage.REGISTER_CAPABILITIES)

        registered = await session.execute(
            select(DeviceCapabilityRow).where(
                DeviceCapabilityRow.device_id == device_id,
                DeviceCapabilityRow.capability_key == capability_key,
            )
        )
        if registered.scalars().first() is None:
            raise UnregisteredCapabilityError(
                f"'{capability_key}' was never registered as a capability of this device."
            )

        expires_at = None
        if ttl_seconds is not None:
            expires_at = _now() + timedelta(seconds=ttl_seconds)

        permission = DevicePermissionRow(
            device_id=device_id,
            capability_key=capability_key,
            granted_at=_now(),
            expires_at=expires_at,
        )
        session.add(permission)
        row.pairing_stage = DevicePairingStage.CONTROL
        await session.commit()
        await session.refresh(permission)

        self._permission_cache[(device_id, capability_key)] = expires_at
        return permission

    async def revoke_permission(
        self, session: AsyncSession, device_id: str, *, capability_key: str
    ) -> None:
        result = await session.execute(
            select(DevicePermissionRow).where(
                DevicePermissionRow.device_id == device_id,
                DevicePermissionRow.capability_key == capability_key,
                DevicePermissionRow.revoked_at.is_(None),
            )
        )
        for permission in result.scalars():
            permission.revoked_at = _now()
        await session.commit()
        self._permission_cache.pop((device_id, capability_key), None)

    def reset_permission_cache(self) -> None:
        """Test-isolation helper — the cache is process-global like every
        other in-memory registry here (see tool_registry's own
        precedent), so a test's grant must not leak into the next one."""
        self._permission_cache.clear()

    def is_permission_valid(self, device_id: str, capability_key: str) -> bool:
        """The one thing a device-control tool executor consults — no DB
        access from inside `ToolExecutor.execute()` (see module
        docstring)."""
        if (device_id, capability_key) not in self._permission_cache:
            return False
        expires_at = self._permission_cache[(device_id, capability_key)]
        return expires_at is None or expires_at > _now()

    async def rebuild_permission_cache_on_startup(self, session: AsyncSession) -> None:
        """Mirrors IntegrationRegistry.reconnect_all_on_startup — a real
        DevicePermission granted before a restart must not silently stop
        working just because the in-memory cache is empty again."""
        result = await session.execute(
            select(DevicePermissionRow).where(DevicePermissionRow.revoked_at.is_(None))
        )
        now = _now()
        for permission in result.scalars():
            if permission.expires_at is not None and permission.expires_at <= now:
                continue
            self._permission_cache[(permission.device_id, permission.capability_key)] = (
                permission.expires_at
            )


# Module-level singleton — mirrors tool_registry/credential_manager.
device_pairing_service = DevicePairingService(credential_manager)
