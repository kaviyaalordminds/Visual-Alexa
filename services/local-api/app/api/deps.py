"""Shared FastAPI dependencies.

Phase 1 is single-local-user (the person who installed VEYRA on this PC —
product brief's local-first, one-PC model). `get_current_user_id` resolves
(and lazily creates) that one local user row rather than implementing
multi-user auth, which is out of Phase 1 scope.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

_LOCAL_USER_DISPLAY_NAME = "Local User"


async def get_or_create_local_user(session: AsyncSession) -> User:
    result = await session.execute(select(User).limit(1))
    user = result.scalars().first()
    if user is not None:
        return user
    user = User(display_name=_LOCAL_USER_DISPLAY_NAME)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
