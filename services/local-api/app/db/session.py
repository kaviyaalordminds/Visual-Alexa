"""Async SQLAlchemy session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# `timeout` (SQLite's busy-timeout, seconds): a real, concurrent writer
# (e.g. a fire-and-forget task from POST /tasks/{id}/run's background
# execution) can legitimately hold a write lock for a brief moment while
# another request reads/writes the same file — without a busy timeout,
# SQLite raises "database is locked" immediately instead of waiting.
engine = create_async_engine(
    settings.database_url, echo=False, future=True, connect_args={"timeout": 15}
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
