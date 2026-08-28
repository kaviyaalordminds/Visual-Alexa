"""GET/POST/PATCH/DELETE /memory. docs/architecture/09-MEMORY.md §2:
user-controlled, inspectable, editable, deletable, auditable. No hidden
memory — every write here is an explicit, attributable API call.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import EventType, MemoryCategory

from app.api.deps import get_or_create_local_user
from app.core.event_bus import event_bus
from app.db.session import get_session
from app.models.memory import Memory as MemoryRow

router = APIRouter(prefix="/memory", tags=["memory"])


async def _publish_memory_updated(action: str, category: MemoryCategory | None) -> None:
    # docs/architecture/09-MEMORY.md §2 — "no hidden memory," every write
    # already goes through this one explicit API. Phase 12 adds an event
    # alongside the existing DB write so a security/memory dashboard can
    # observe changes in real time, without a second write path.
    await event_bus.publish_type(
        EventType.MEMORY_UPDATED,
        str(uuid4()),
        {"action": action, "category": category.value if category else None},
    )


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
    await _publish_memory_updated("created", row.category)
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
    await _publish_memory_updated("updated", row.category)
    return MemoryOut.model_validate(row)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, session: AsyncSession = Depends(get_session)) -> None:
    result = await session.execute(select(MemoryRow).where(MemoryRow.id == memory_id))
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown memory record '{memory_id}'.")
    category = row.category
    await session.delete(row)
    await session.commit()
    await _publish_memory_updated("deleted", category)


@router.delete("", status_code=200)
async def clear_memory(
    category: MemoryCategory | None = None, session: AsyncSession = Depends(get_session)
) -> dict[str, int]:
    """Phase 12 §21 — a bulk 'clear' operation, distinct from per-record
    delete above. `category=None` clears every category (a full memory
    wipe); passing `category` scopes it to just that one ("disable"/
    reset a single category's stored records). Returns the count deleted
    so a caller/UI can confirm the scope of what just happened."""
    stmt = select(MemoryRow)
    if category is not None:
        stmt = stmt.where(MemoryRow.category == category)
    result = await session.execute(stmt)
    rows = list(result.scalars())
    for row in rows:
        await session.delete(row)
    await session.commit()
    await _publish_memory_updated("cleared", category)
    return {"deleted": len(rows)}
