"""IntegrationRegistry — docs/phase-7/INTEGRATION-ARCHITECTURE.md.

Unlike ToolRegistry (pure in-memory, rebuilt from code at every process
start), integrations need to survive a restart already CONNECTED — the
user shouldn't have to reconnect Gmail every time VEYRA restarts. This is
therefore a thin service over the real `integrations` table, not an
in-memory singleton; `Integration.provider` is the natural key
(`IntegrationDefinition.id`).

docs/architecture/11-INTEGRATIONS.md §2's invariant holds here exactly:
every tool an integration exposes is registered in the *same*
`ToolRegistry` every other tool uses, gated by the *same* Policy Engine —
`connect`/`disconnect` only ever call `tool_registry.register`/
`unregister`, never a second execution path.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import (
    ConnectionResult,
    IntegrationDefinition,
    IntegrationState,
    ToolDefinition,
)

from app.models.integration import Integration as IntegrationRow
from app.services.credential_manager import CredentialManager, credential_manager
from app.services.tool_registry import ToolExecutor, ToolRegistry

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class IntegrationBundle:
    """What an integration IS (`definition`) and what it exposes once
    connected. `tool_definitions` is static — it never depends on which
    credential is currently connected, only `build_executor` does (an
    executor bound to *this* connection's credential ref)."""

    definition: IntegrationDefinition
    tool_definitions: list[ToolDefinition]
    build_executor: Callable[[ToolDefinition, str], ToolExecutor]


class UnknownIntegrationError(LookupError):
    pass


class IntegrationRegistry:
    def __init__(self, credential_manager: CredentialManager) -> None:
        self._credential_manager = credential_manager
        self._bundles: dict[str, IntegrationBundle] = {}

    def register_definition(self, bundle: IntegrationBundle) -> None:
        self._bundles[bundle.definition.id] = bundle

    def list_definitions(self) -> list[IntegrationDefinition]:
        return [b.definition for b in self._bundles.values()]

    def get_definition(self, integration_id: str) -> IntegrationDefinition | None:
        bundle = self._bundles.get(integration_id)
        return bundle.definition if bundle else None

    async def get_row(self, session: AsyncSession, integration_id: str) -> IntegrationRow | None:
        result = await session.execute(
            select(IntegrationRow).where(IntegrationRow.provider == integration_id)
        )
        return result.scalars().first()

    async def list_rows(self, session: AsyncSession) -> list[IntegrationRow]:
        result = await session.execute(select(IntegrationRow))
        return list(result.scalars())

    async def connect(
        self,
        session: AsyncSession,
        tool_registry: ToolRegistry,
        integration_id: str,
        *,
        secret: str,
    ) -> ConnectionResult:
        bundle = self._bundles.get(integration_id)
        if bundle is None:
            return ConnectionResult(
                success=False,
                state=IntegrationState.UNAVAILABLE,
                reason=f"Unknown integration '{integration_id}'.",
            )

        row = await self.get_row(session, integration_id)
        if row is None:
            row = IntegrationRow(
                provider=integration_id, auth_method=bundle.definition.auth_method
            )
            session.add(row)

        # Rotating credential: drop the old one rather than leaking it.
        if row.credentials_ref:
            self._credential_manager.delete_credential(row.credentials_ref)

        ref = self._credential_manager.store_credential(secret)
        row.name = bundle.definition.name
        row.auth_method = bundle.definition.auth_method
        row.connected = True
        row.state = IntegrationState.CONNECTED
        row.scopes = list(bundle.definition.required_scopes)
        row.credentials_ref = ref
        row.connected_at = _now()
        await session.commit()

        for tool_def in bundle.tool_definitions:
            tool_registry.register(tool_def, bundle.build_executor(tool_def, ref))

        return ConnectionResult(success=True, state=IntegrationState.CONNECTED)

    async def disconnect(
        self, session: AsyncSession, tool_registry: ToolRegistry, integration_id: str
    ) -> ConnectionResult:
        bundle = self._bundles.get(integration_id)
        if bundle is None:
            return ConnectionResult(
                success=False,
                state=IntegrationState.UNAVAILABLE,
                reason=f"Unknown integration '{integration_id}'.",
            )

        row = await self.get_row(session, integration_id)
        if row is None or not row.connected:
            return ConnectionResult(
                success=False, state=IntegrationState.DISCONNECTED, reason="Not connected."
            )

        if row.credentials_ref:
            self._credential_manager.delete_credential(row.credentials_ref)
        row.connected = False
        row.state = IntegrationState.DISCONNECTED
        row.credentials_ref = None
        await session.commit()

        for tool_def in bundle.tool_definitions:
            tool_registry.unregister(tool_def.id)

        return ConnectionResult(success=True, state=IntegrationState.DISCONNECTED)

    async def health_check(self, session: AsyncSession, integration_id: str) -> IntegrationState:
        row = await self.get_row(session, integration_id)
        if row is None:
            return IntegrationState.UNAVAILABLE
        if not row.connected:
            return IntegrationState.DISCONNECTED
        if row.credentials_ref is None or not self._credential_manager.validate_credential(
            row.credentials_ref
        ):
            row.state = IntegrationState.EXPIRED
            await session.commit()
            return IntegrationState.EXPIRED
        row.last_health_check_at = _now()
        await session.commit()
        return IntegrationState.CONNECTED

    async def reconnect_all_on_startup(
        self, session: AsyncSession, tool_registry: ToolRegistry
    ) -> None:
        """docs/phase-7/PHASE-7-IMPLEMENTATION-PLAN.md §3.2 — the same
        'DB rows -> in-memory object, rebuilt wholesale at boot' pattern
        `application_registry.py` already established: an integration a
        user connected before a restart should not silently lose its
        tools just because the process restarted. A credential that no
        longer validates is surfaced as EXPIRED rather than silently
        re-registering tools that would immediately fail NOT_CONNECTED.

        Per CLAUDE.md, an optional subsystem (an integration a user has
        connected) must never be able to block Local API startup. Each
        row is therefore fault-isolated: an unexpected error reconnecting
        one integration is logged and skipped rather than propagated, so
        a single malformed/broken row cannot abort startup for every
        other integration or for the app as a whole."""
        for row in await self.list_rows(session):
            if not row.connected:
                continue
            try:
                bundle = self._bundles.get(row.provider)
                if bundle is None:
                    continue
                if row.credentials_ref is None or not self._credential_manager.validate_credential(
                    row.credentials_ref
                ):
                    row.connected = False
                    row.state = IntegrationState.EXPIRED
                    continue
                for tool_def in bundle.tool_definitions:
                    tool_registry.register(
                        tool_def, bundle.build_executor(tool_def, row.credentials_ref)
                    )
            except Exception:
                logger.exception(
                    "[VEYRA] Integration reconnect failed for '%s' — skipping, startup continues.",
                    row.provider,
                )
        await session.commit()


# Module-level singleton — mirrors tool_registry/policy_engine/event_bus.
integration_registry = IntegrationRegistry(credential_manager)
