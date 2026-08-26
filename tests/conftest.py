"""Root pytest fixtures for the whole monorepo test suite (product brief
§30). Points the Local API at a fresh temp SQLite database per test so
tests never touch a developer's real veyra.db, and resets schema + seed
data between tests for isolation.
"""

from __future__ import annotations

import os
import tempfile

import pytest
import pytest_asyncio

_TMP_DB_FD, _TMP_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_TMP_DB_FD)
os.environ["VEYRA_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB_PATH}"
os.environ.setdefault("VEYRA_SECRET_KEY", "test-only-secret")

from app.db.base import Base
from app.db.seed_defaults import DEFAULT_SETTINGS
from app.db.session import SessionLocal, engine
from app.main import app as fastapi_app
from app.models.setting import SystemSetting
from app.services.bootstrap import register_default_tools
from app.services.tool_registry import tool_registry


@pytest_asyncio.fixture(autouse=True)
async def _reset_state():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        for key, value in DEFAULT_SETTINGS.items():
            session.add(SystemSetting(key=key, value=value))
        await session.commit()

    register_default_tools(tool_registry)
    yield


@pytest_asyncio.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
