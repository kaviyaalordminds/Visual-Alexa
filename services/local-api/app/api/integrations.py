"""GET /integrations, POST /integrations/{id}/connect|disconnect|
health-check. docs/phase-7/INTEGRATION-ARCHITECTURE.md.

Every integration-backed tool call still goes through the exact same
ToolRegistry -> PolicyEngine -> execute_tool_call chain
`POST /tools/{tool_id}/invoke` already uses — these routes only manage
the *connection* (credential + tool registration), never a second
execution path.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import AuthMethod, IntegrationDefinition, IntegrationState, ToolCategory

from app.db.session import get_session
from app.models.integration import Integration as IntegrationRow
from app.services.integration_registry import integration_registry
from app.services.tool_registry import tool_registry

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationOut(BaseModel):
    id: str
    name: str
    category: ToolCategory
    auth_method: AuthMethod
    description: str
    state: IntegrationState
    connected: bool
    scopes: list[str]
    connected_at: datetime | None
    last_health_check_at: datetime | None


class ConnectRequest(BaseModel):
    secret: str


def _to_out(definition: IntegrationDefinition, row: IntegrationRow | None) -> IntegrationOut:
    return IntegrationOut(
        id=definition.id,
        name=definition.name,
        category=definition.category,
        auth_method=definition.auth_method,
        description=definition.description,
        state=row.state if row is not None else IntegrationState.CONNECT_REQUIRED,
        connected=row.connected if row is not None else False,
        scopes=list(row.scopes) if row is not None and row.scopes else [],
        connected_at=row.connected_at if row is not None else None,
        last_health_check_at=row.last_health_check_at if row is not None else None,
    )


async def _build_out(session: AsyncSession, integration_id: str) -> IntegrationOut:
    definition = integration_registry.get_definition(integration_id)
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration '{integration_id}'.")
    row = await integration_registry.get_row(session, integration_id)
    return _to_out(definition, row)


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(session: AsyncSession = Depends(get_session)) -> list[IntegrationOut]:
    rows = {row.provider: row for row in await integration_registry.list_rows(session)}
    return [
        _to_out(definition, rows.get(definition.id))
        for definition in integration_registry.list_definitions()
    ]


@router.post("/{integration_id}/connect", response_model=IntegrationOut)
async def connect_integration(
    integration_id: str, body: ConnectRequest, session: AsyncSession = Depends(get_session)
) -> IntegrationOut:
    result = await integration_registry.connect(
        session, tool_registry, integration_id, secret=body.secret
    )
    if not result.success:
        raise HTTPException(status_code=404, detail=result.reason or "Could not connect.")
    return await _build_out(session, integration_id)


@router.post("/{integration_id}/disconnect", response_model=IntegrationOut)
async def disconnect_integration(
    integration_id: str, session: AsyncSession = Depends(get_session)
) -> IntegrationOut:
    result = await integration_registry.disconnect(session, tool_registry, integration_id)
    if not result.success:
        code = 404 if integration_registry.get_definition(integration_id) is None else 409
        raise HTTPException(status_code=code, detail=result.reason or "Could not disconnect.")
    return await _build_out(session, integration_id)


@router.post("/{integration_id}/health-check", response_model=IntegrationOut)
async def health_check_integration(
    integration_id: str, session: AsyncSession = Depends(get_session)
) -> IntegrationOut:
    if integration_registry.get_definition(integration_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration '{integration_id}'.")
    await integration_registry.health_check(session, integration_id)
    return await _build_out(session, integration_id)
