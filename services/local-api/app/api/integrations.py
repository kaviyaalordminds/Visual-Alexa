"""GET /integrations. docs/architecture/11-INTEGRATIONS.md — no live
integration is connected in Phase 1; this lists the (empty) registry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.integration import Integration as IntegrationRow

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationOut(BaseModel):
    id: str
    provider: str
    auth_method: str
    connected: bool

    model_config = {"from_attributes": True}


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(session: AsyncSession = Depends(get_session)) -> list[IntegrationOut]:
    result = await session.execute(select(IntegrationRow))
    return [IntegrationOut.model_validate(row) for row in result.scalars()]
