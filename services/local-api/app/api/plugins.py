"""GET /plugins, POST /plugins/install|{id}/trust|{id}/permissions/
grant|revoke|{id}/enable|{id}/disable, DELETE /plugins/{id}.
docs/phase-7/PLUGIN-ARCHITECTURE.md.

`POST /plugins/install` never accepts or executes plugin code — see
`PluginRegistry.install`'s own docstring. A plugin installed through
this route is metadata/permissions only until a matching, server-side
tool builder already shipped with this process claims it (none do yet
in this phase — see `docs/phase-7/PHASE-7-TEST-RESULTS.md`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import PluginManifest, PluginState

from app.db.session import get_session
from app.services.plugin_registry import (
    IllegalPluginStateError,
    PermissionNotRequestedError,
    UnknownPluginError,
    plugin_registry,
)
from app.services.tool_registry import tool_registry

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginPermissionOut(BaseModel):
    permission: str
    granted: bool


class PluginOut(BaseModel):
    id: str
    manifest_id: str
    name: str
    version: str
    author: str
    state: PluginState
    permissions: list[PluginPermissionOut]


class InstallRequest(BaseModel):
    manifest: PluginManifest


class PermissionRequest(BaseModel):
    permission: str


def _handle_plugin_error(exc: Exception) -> HTTPException:
    if isinstance(exc, UnknownPluginError):
        return HTTPException(status_code=404, detail=f"Unknown plugin '{exc}'.")
    if isinstance(exc, PermissionNotRequestedError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, IllegalPluginStateError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))  # pragma: no cover - defensive


async def _to_out(session: AsyncSession, plugin_id: str) -> PluginOut:
    row = await plugin_registry.get(session, plugin_id)
    permissions = await plugin_registry.list_permissions(session, plugin_id)
    return PluginOut(
        id=row.id,
        manifest_id=row.manifest_id,
        name=row.name,
        version=row.version,
        author=row.author,
        state=row.state,
        permissions=[
            PluginPermissionOut(permission=p.permission, granted=p.granted) for p in permissions
        ],
    )


@router.get("", response_model=list[PluginOut])
async def list_plugins(session: AsyncSession = Depends(get_session)) -> list[PluginOut]:
    rows = await plugin_registry.list_installed(session)
    return [await _to_out(session, row.id) for row in rows]


@router.post("/install", response_model=PluginOut, status_code=201)
async def install_plugin(
    body: InstallRequest, session: AsyncSession = Depends(get_session)
) -> PluginOut:
    row = await plugin_registry.install(session, body.manifest)
    return await _to_out(session, row.id)


@router.post("/{plugin_id}/trust", response_model=PluginOut)
async def trust_plugin(plugin_id: str, session: AsyncSession = Depends(get_session)) -> PluginOut:
    try:
        await plugin_registry.mark_trusted(session, plugin_id)
    except (UnknownPluginError, IllegalPluginStateError) as exc:
        raise _handle_plugin_error(exc) from exc
    return await _to_out(session, plugin_id)


@router.post("/{plugin_id}/permissions/grant", response_model=PluginOut)
async def grant_permission(
    plugin_id: str, body: PermissionRequest, session: AsyncSession = Depends(get_session)
) -> PluginOut:
    try:
        await plugin_registry.grant(session, plugin_id, body.permission)
    except (UnknownPluginError, PermissionNotRequestedError) as exc:
        raise _handle_plugin_error(exc) from exc
    return await _to_out(session, plugin_id)


@router.post("/{plugin_id}/permissions/revoke", response_model=PluginOut)
async def revoke_permission(
    plugin_id: str, body: PermissionRequest, session: AsyncSession = Depends(get_session)
) -> PluginOut:
    await plugin_registry.revoke_permission(session, plugin_id, body.permission)
    return await _to_out(session, plugin_id)


@router.post("/{plugin_id}/enable", response_model=PluginOut)
async def enable_plugin(plugin_id: str, session: AsyncSession = Depends(get_session)) -> PluginOut:
    try:
        await plugin_registry.enable(session, tool_registry, plugin_id)
    except (UnknownPluginError, IllegalPluginStateError) as exc:
        raise _handle_plugin_error(exc) from exc
    return await _to_out(session, plugin_id)


@router.post("/{plugin_id}/disable", response_model=PluginOut)
async def disable_plugin(plugin_id: str, session: AsyncSession = Depends(get_session)) -> PluginOut:
    try:
        await plugin_registry.disable(session, tool_registry, plugin_id)
    except UnknownPluginError as exc:
        raise _handle_plugin_error(exc) from exc
    return await _to_out(session, plugin_id)


@router.delete("/{plugin_id}", status_code=204)
async def remove_plugin(plugin_id: str, session: AsyncSession = Depends(get_session)) -> None:
    try:
        await plugin_registry.remove(session, tool_registry, plugin_id)
    except UnknownPluginError as exc:
        raise _handle_plugin_error(exc) from exc
