"""PluginRegistry — docs/phase-7/PLUGIN-ARCHITECTURE.md.

Default-deny, always (brief §63/§65): `install()` always lands a plugin
in UNTRUSTED with zero granted permissions, regardless of what its own
manifest requests. A plugin's manifest is the *ceiling* of what it can
ever be granted — `grant()` refuses any permission the manifest didn't
itself request, and `enable()` only ever registers a tool into the real
`ToolRegistry` when its `required_permission` is one of the plugin's
currently-granted permissions. A tool whose permission was requested but
never granted (or granted then revoked) simply never goes live — denial
by omission, the same shape `ToolRegistry.disable()` already uses for
ordinary tools.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import PluginManifest, PluginState, ToolDefinition

from app.models.plugin import Plugin as PluginRow
from app.models.plugin import PluginPermission as PluginPermissionRow
from app.services.tool_registry import ToolExecutor, ToolRegistry

ToolBuilder = Callable[[], list[tuple[ToolDefinition, ToolExecutor]]]


class UnknownPluginError(LookupError):
    pass


class PermissionNotRequestedError(ValueError):
    """A caller tried to grant a plugin a permission its own manifest
    never requested — brief §66: the requested set is shown to the user
    before install, and it is also the ceiling of what can ever be
    granted, never expandable after the fact."""


class IllegalPluginStateError(ValueError):
    pass


class PluginRegistry:
    def __init__(self) -> None:
        self._tool_builders: dict[str, ToolBuilder] = {}

    async def install(
        self,
        session: AsyncSession,
        manifest: PluginManifest,
        *,
        tool_builder: ToolBuilder | None = None,
    ) -> PluginRow:
        """docs/security/07-PROMPT-INJECTION.md, brief §69 — 'never
        execute plugin code directly from... a downloaded file without
        validation.' `tool_builder` can therefore only ever come from a
        server-side Python call, never an HTTP request body:
        `app/api/plugins.py`'s `POST /plugins/install` route always
        installs with no builder at all (metadata/permissions only,
        tracked and grantable, but incapable of ever registering a live
        tool)."""
        row = PluginRow(
            manifest_id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            author=manifest.author,
            state=PluginState.UNTRUSTED,
            manifest=manifest.model_dump(mode="json"),
        )
        session.add(row)
        await session.flush()  # populate row.id (a Python-side default,
        # only assigned at flush) before referencing it below.
        for permission in manifest.permissions:
            session.add(PluginPermissionRow(plugin_id=row.id, permission=permission, granted=False))
        await session.commit()
        await session.refresh(row)
        if tool_builder is not None:
            self._tool_builders[row.id] = tool_builder
        return row

    async def get(self, session: AsyncSession, plugin_id: str) -> PluginRow:
        result = await session.execute(select(PluginRow).where(PluginRow.id == plugin_id))
        row = result.scalars().first()
        if row is None:
            raise UnknownPluginError(plugin_id)
        return row

    async def list_installed(self, session: AsyncSession) -> list[PluginRow]:
        result = await session.execute(select(PluginRow))
        return list(result.scalars())

    async def list_permissions(
        self, session: AsyncSession, plugin_id: str
    ) -> list[PluginPermissionRow]:
        result = await session.execute(
            select(PluginPermissionRow).where(PluginPermissionRow.plugin_id == plugin_id)
        )
        return list(result.scalars())

    async def grant(self, session: AsyncSession, plugin_id: str, permission: str) -> None:
        await self.get(session, plugin_id)  # 404s on an unknown plugin
        result = await session.execute(
            select(PluginPermissionRow).where(
                PluginPermissionRow.plugin_id == plugin_id,
                PluginPermissionRow.permission == permission,
            )
        )
        row = result.scalars().first()
        if row is None:
            raise PermissionNotRequestedError(
                f"'{permission}' was never requested by this plugin's manifest."
            )
        row.granted = True
        await session.commit()

    async def revoke_permission(
        self, session: AsyncSession, plugin_id: str, permission: str
    ) -> None:
        result = await session.execute(
            select(PluginPermissionRow).where(
                PluginPermissionRow.plugin_id == plugin_id,
                PluginPermissionRow.permission == permission,
            )
        )
        row = result.scalars().first()
        if row is not None:
            row.granted = False
            await session.commit()

    async def mark_trusted(self, session: AsyncSession, plugin_id: str) -> PluginRow:
        """The extension point a real review process would call — this
        skeleton makes no automated trust decision of its own (brief §63:
        'do not treat every plugin as trusted')."""
        row = await self.get(session, plugin_id)
        if row.state not in (PluginState.UNTRUSTED, PluginState.REVIEW_REQUIRED):
            raise IllegalPluginStateError(f"Cannot trust a plugin in state '{row.state.value}'.")
        row.state = PluginState.TRUSTED
        await session.commit()
        return row

    async def enable(
        self, session: AsyncSession, tool_registry: ToolRegistry, plugin_id: str
    ) -> PluginRow:
        row = await self.get(session, plugin_id)
        if row.state not in (PluginState.TRUSTED, PluginState.DISABLED):
            raise IllegalPluginStateError(
                f"Cannot enable a plugin in state '{row.state.value}' — it must be TRUSTED first."
            )
        granted = {
            p.permission for p in await self.list_permissions(session, plugin_id) if p.granted
        }
        builder = self._tool_builders.get(plugin_id)
        if builder is not None:
            for tool_def, executor in builder():
                if tool_def.required_permission in granted:
                    tool_registry.register(tool_def, executor)
        row.state = PluginState.ENABLED
        await session.commit()
        return row

    async def disable(
        self, session: AsyncSession, tool_registry: ToolRegistry, plugin_id: str
    ) -> PluginRow:
        row = await self.get(session, plugin_id)
        builder = self._tool_builders.get(plugin_id)
        if builder is not None:
            for tool_def, _ in builder():
                tool_registry.unregister(tool_def.id)
        row.state = PluginState.DISABLED
        await session.commit()
        return row

    async def remove(
        self, session: AsyncSession, tool_registry: ToolRegistry, plugin_id: str
    ) -> None:
        """brief §67 — disable tools, revoke credentials, remove
        registrations, clear temporary resources."""
        row = await self.get(session, plugin_id)
        builder = self._tool_builders.pop(plugin_id, None)
        if builder is not None:
            for tool_def, _ in builder():
                tool_registry.unregister(tool_def.id)
        for permission in await self.list_permissions(session, plugin_id):
            await session.delete(permission)
        await session.delete(row)
        await session.commit()


# Module-level singleton — mirrors tool_registry/integration_registry.
plugin_registry = PluginRegistry()
