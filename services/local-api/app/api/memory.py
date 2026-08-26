"""GET/POST/PATCH/DELETE /memory. docs/architecture/09-MEMORY.md §2:
user-controlled, inspectable, editable, deletable, auditable. No hidden
memory — every write here is an explicit, attributable API call.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import MemoryCategory

from app.api.deps import get_or_create_local_user
from app.db.session import get_session
from app.models.memory import Memory as MemoryRow

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryOut(BaseModel):
    id: str
    category: MemoryCategory
    key: str | None
    content: dict[str, Any]
    source: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class MemoryCreate(BaseModel):
    category: MemoryCategory
    key: str | None = None
    content: dict[str, Any]
    source: str


class MemoryUpdate(BaseModel):
    content: dict[str, Any]


@router.get("", response_model=list[MemoryOut])
async def list_memory(
    category: MemoryCategory | None = None, session: AsyncSession = Depends(get_session)
) -> list[MemoryOut]:
    stmt = select(MemoryRow)
    if category is not None:
        stmt = stmt.where(MemoryRow.category == category)
    result = await session.execute(stmt)
    return [MemoryOut.model_validate(row) for row in result.scalars()]


@router.post("", response_model=MemoryOut, status_code=201)
async def create_memory(
    body: MemoryCreate, session: AsyncSession = Depends(get_session)
) -> MemoryOut:
    user = await get_or_create_local_user(session)
    row = MemoryRow(
        user_id=user.id,
        category=body.category,
        key=body.key,
        content=body.content,
        source=body.source,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return MemoryOut.model_validate(row)


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: str, body: MemoryUpdate, session: AsyncSession = Depends(get_session)
) -> MemoryOut:
    result = await session.execute(select(MemoryRow).where(MemoryRow.id == memory_id))
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown memory record '{memory_id}'.")
    row.content = body.content
    await session.commit()
    await session.refresh(row)
    return MemoryOut.model_validate(row)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, session: AsyncSession = Depends(get_session)) -> None:
    result = await session.execute(select(MemoryRow).where(MemoryRow.id == memory_id))
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown memory record '{memory_id}'.")
    await session.delete(row)
    await session.commit()
