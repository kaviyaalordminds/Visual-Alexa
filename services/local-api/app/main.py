"""VEYRA Local API entry point.

CLAUDE.md: 'The Local API binds to loopback (127.0.0.1) only.'
docs/architecture/01-SYSTEM-ARCHITECTURE.md: the Local API is the only
process with database access and the only process that can invoke a tool.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    conversations,
    devices,
    events,
    health,
    integrations,
    memory,
    system,
    tasks,
    tools,
)
from app.api import permissions as permissions_router
from app.api import settings as settings_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.bootstrap import register_default_tools
from app.services.tool_registry import tool_registry

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    register_default_tools(tool_registry)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="VEYRA Local API — Phase 1 foundation. "
        "See docs/architecture/01-SYSTEM-ARCHITECTURE.md.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(system.router)
    app.include_router(settings_router.router)
    app.include_router(tools.router)
    app.include_router(permissions_router.router)
    app.include_router(memory.router)
    app.include_router(devices.router)
    app.include_router(conversations.router)
    app.include_router(tasks.router)
    app.include_router(integrations.router)
    app.include_router(events.router)

    return app


app = create_app()
