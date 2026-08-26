"""GET/POST /conversations, GET/POST /conversations/{id}/messages."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_or_create_local_user
from app.db.session import get_session
from app.models.conversation import Conversation as ConversationRow
from app.models.conversation import Message as MessageRow

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationOut(BaseModel):
    id: str
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str | None = None


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


@router.get("", response_model=list[ConversationOut])
async def list_conversations(session: AsyncSession = Depends(get_session)) -> list[ConversationOut]:
    result = await session.execute(select(ConversationRow))
    return [ConversationOut.model_validate(row) for row in result.scalars()]


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate, session: AsyncSession = Depends(get_session)
) -> ConversationOut:
    user = await get_or_create_local_user(session)
    row = ConversationRow(user_id=user.id, title=body.title)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ConversationOut.model_validate(row)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: str, session: AsyncSession = Depends(get_session)
) -> list[MessageOut]:
    result = await session.execute(
        select(MessageRow).where(MessageRow.conversation_id == conversation_id)
    )
    return [MessageOut.model_validate(row) for row in result.scalars()]


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=201)
async def create_message(
    conversation_id: str, body: MessageCreate, session: AsyncSession = Depends(get_session)
) -> MessageOut:
    result = await session.execute(
        select(ConversationRow).where(ConversationRow.id == conversation_id)
    )
    if result.scalars().first() is None:
        raise HTTPException(status_code=404, detail=f"Unknown conversation '{conversation_id}'.")
    row = MessageRow(conversation_id=conversation_id, role=body.role, content=body.content)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return MessageOut.model_validate(row)
