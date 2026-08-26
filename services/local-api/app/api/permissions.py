"""GET /permissions, POST /permissions, POST /permissions/{id}/revoke.
docs/security/02-PERMISSION-MODEL.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import PermissionDecision, RiskLevel

from app.api.deps import get_or_create_local_user
from app.db.session import get_session
from app.models.tool import PermissionGrant as PermissionGrantRow

router = APIRouter(prefix="/permissions", tags=["permissions"])


class GrantOut(BaseModel):
    id: str
    tool_id: str
    target: str | None
    risk_level: RiskLevel
    scope: PermissionDecision
    granted_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class GrantCreate(BaseModel):
    tool_id: str
    target: str | None = None
    risk_level: RiskLevel
    scope: PermissionDecision
    expires_at: datetime | None = None


@router.get("", response_model=list[GrantOut])
async def list_grants(session: AsyncSession = Depends(get_session)) -> list[GrantOut]:
    result = await session.execute(select(PermissionGrantRow))
    return [GrantOut.model_validate(row) for row in result.scalars()]


@router.post("", response_model=GrantOut, status_code=201)
async def create_grant(
    body: GrantCreate, session: AsyncSession = Depends(get_session)
) -> GrantOut:
    if body.risk_level == RiskLevel.CRITICAL:
        # docs/security/08-SENSITIVE-ACTION-POLICY.md §2 — no grant may
        # ever pre-authorize a CRITICAL action.
        raise HTTPException(
            status_code=400,
            detail="CRITICAL-risk actions cannot be pre-authorized via a stored grant; "
            "they always require fresh, explicit confirmation at call time.",
        )
    user = await get_or_create_local_user(session)
    row = PermissionGrantRow(
        user_id=user.id,
        tool_id=body.tool_id,
        target=body.target,
        risk_level=body.risk_level,
        scope=body.scope,
        granted_at=datetime.now(UTC),
        expires_at=body.expires_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return GrantOut.model_validate(row)


@router.post("/{grant_id}/revoke", response_model=GrantOut)
async def revoke_grant(
    grant_id: str, session: AsyncSession = Depends(get_session)
) -> GrantOut:
    result = await session.execute(
        select(PermissionGrantRow).where(PermissionGrantRow.id == grant_id)
    )
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown grant '{grant_id}'.")
    row.revoked_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return GrantOut.model_validate(row)
