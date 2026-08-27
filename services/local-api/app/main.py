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
    plugins,
    system,
    tasks,
    tools,
    voice,
)
from app.api import permissions as permissions_router
from app.api import settings as settings_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.agent.register import init_orchestrator
from app.services.application_registry import load_application_registry
from app.services.bootstrap import register_default_tools
from app.services.computer_control import register_computer_control_tools
from app.services.computer_control.backends import build_backend_bundle
from app.services.credential_manager import credential_manager
from app.services.device_pairing import device_pairing_service
from app.services.integration_registry import integration_registry
from app.services.mock_iot import build_mock_iot_tools
from app.services.reference_integration import build_reference_integration_bundle
from app.services.tool_registry import tool_registry
from app.services.vision import register_vision_tools
from app.services.voice.register import init_voice_manager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    register_default_tools(tool_registry)
    async with SessionLocal() as session:
        application_registry = await load_application_registry(session)
    bundle = build_backend_bundle()
    register_computer_control_tools(tool_registry, settings, application_registry, bundle=bundle)
    register_vision_tools(tool_registry, bundle)
    integration_registry.register_definition(build_reference_integration_bundle(credential_manager))
    for mock_definition, mock_executor in build_mock_iot_tools(device_pairing_service):
        tool_registry.register(mock_definition, mock_executor)
    async with SessionLocal() as session:
        await integration_registry.reconnect_all_on_startup(session, tool_registry)
        await device_pairing_service.rebuild_permission_cache_on_startup(session)
    init_orchestrator(tool_registry, settings)
    init_voice_manager()
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
    app.include_router(plugins.router)
    app.include_router(events.router)
    app.include_router(voice.router)

    return app


app = create_app()
