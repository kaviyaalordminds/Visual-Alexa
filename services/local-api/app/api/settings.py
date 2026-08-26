"""GET/PATCH /settings — docs/security/05-DATA-PROTECTION.md §3.

Only a fixed, known set of settings keys may be toggled through this API —
arbitrary key creation is rejected, so this endpoint cannot become a way to
silently add new hidden state.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.setting import SystemSetting

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingOut(BaseModel):
    key: str
    value: Any

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: Any


@router.get("", response_model=list[SettingOut])
async def list_settings(session: AsyncSession = Depends(get_session)) -> list[SettingOut]:
    result = await session.execute(select(SystemSetting).order_by(SystemSetting.key))
    return [SettingOut.model_validate(row) for row in result.scalars()]


@router.patch("/{key}", response_model=SettingOut)
async def update_setting(
    key: str, body: SettingUpdate, session: AsyncSession = Depends(get_session)
) -> SettingOut:
    result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown setting key '{key}'.")
    row.value = body.value
    await session.commit()
    await session.refresh(row)
    return SettingOut.model_validate(row)
