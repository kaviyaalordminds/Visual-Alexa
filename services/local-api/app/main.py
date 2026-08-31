"""VEYRA Local API entry point.

CLAUDE.md: 'The Local API binds to loopback (127.0.0.1) only.'
docs/architecture/01-SYSTEM-ARCHITECTURE.md: the Local API is the only
process with database access and the only process that can invoke a tool.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from computer_control.core.capabilities import detect_capabilities
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import browser as browser_api
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
from app.api.events import close_all_websockets
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.readiness import mark_not_ready, mark_ready, mark_started
from app.core.version import BACKEND_VERSION
from app.db.migrate import DatabaseInitializationError, ensure_database_ready
from app.db.session import SessionLocal, engine
from app.models.setting import SystemSetting
from app.services.agent.register import init_orchestrator
from app.services.application_registry import load_application_registry
from app.services.bootstrap import register_default_tools
from app.services.browser.manager import browser_manager
from app.services.browser.register import register_browser_tools
from app.services.computer_control import register_computer_control_tools
from app.services.computer_control.backends import build_backend_bundle
from app.services.credential_manager import credential_manager
from app.services.device_pairing import device_pairing_service
from app.services.integration_registry import integration_registry
from app.services.mock_iot import build_mock_iot_tools
from app.services.iot.ha_tools import build_ha_tools
from app.services.reference_integration import build_reference_integration_bundle
from app.services.subsystem_diagnostics_tools import register_subsystem_diagnostic_tools
from app.services.agent.llm_provider import NotConfiguredLLMProvider
from app.services.agent.providers import build_llm_provider
from app.services.subsystem_health import (
    compute_ai_status,
    compute_computer_control_status,
    compute_iot_status,
    compute_vision_status,
    compute_voice_status,
    record_ai_check_result,
)
from app.services.tool_registry import tool_registry
from app.services.vision import register_vision_tools
from app.services.voice.register import (
    build_and_start_voice_pipeline,
    init_voice_manager,
    stop_voice_pipeline,
)

settings = get_settings()
logger = logging.getLogger(__name__)


async def _startup_ai_health_check() -> None:
    """Run an AI connectivity probe shortly after startup so /system shows
    CONNECTED (or ERROR) on the first frontend poll without the user having to
    invoke system.ai_health_check manually.  Retries once after 15 s to
    tolerate a local model server (Ollama, LM Studio) that is still warming
    up when the API starts.  Intentionally non-fatal: a failure here must
    never prevent the API from serving requests."""
    await asyncio.sleep(5)
    for attempt in range(2):
        try:
            provider = build_llm_provider(settings)
            if isinstance(provider, NotConfiguredLLMProvider):
                return
            result = await provider.health_check()
            record_ai_check_result(result)
            logger.info(
                "[AI] startup health-check (attempt %d): %s — %s",
                attempt + 1,
                "CONNECTED" if result.available else "ERROR",
                result.reason,
            )
            if result.available:
                return
        except Exception as exc:
            logger.warning("[AI] startup health-check (attempt %d) failed: %s", attempt + 1, exc)
        if attempt == 0:
            await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mark_started()
    configure_logging(settings.log_level)
    logger.info("[VEYRA] Starting Local API")
    logger.info("[VEYRA] Version: %s", BACKEND_VERSION)
    logger.info("[VEYRA] Environment: %s", settings.environment)
    logger.info("[VEYRA] Database: %s", settings.database_url)

    # CRITICAL — every other startup step queries this database (starting
    # with load_application_registry() a few lines down); none of them
    # can tolerate a missing/stale schema, so this must be the first real
    # I/O the app performs and a failure here must stop startup, not be
    # swallowed. See app/db/migrate.py's own docstring for exactly which
    # startup bug this fixes.
    try:
        ensure_database_ready(settings)
    except DatabaseInitializationError as exc:
        logger.error("[VEYRA] STARTUP FAILED")
        logger.error("[VEYRA] Reason: %s", exc.reason)
        logger.error("[VEYRA] Resolution: %s", exc.resolution)
        raise

    register_default_tools(tool_registry)
    register_subsystem_diagnostic_tools(tool_registry)
    async with SessionLocal() as session:
        application_registry = await load_application_registry(session)
    logger.info(
        "[VEYRA] Application registry: READY (%d applications)",
        len(application_registry.list_entries()),
    )
    bundle = build_backend_bundle()
    register_computer_control_tools(tool_registry, settings, application_registry, bundle=bundle)
    register_vision_tools(tool_registry, bundle)
    integration_registry.register_definition(build_reference_integration_bundle(credential_manager))
    for mock_definition, mock_executor in build_mock_iot_tools(device_pairing_service):
        tool_registry.register(mock_definition, mock_executor)
    # Real Home Assistant IoT tools — only registered when HA is configured.
    if settings.ha_base_url and settings.ha_token:
        for ha_def, ha_exec in build_ha_tools():
            tool_registry.register(ha_def, ha_exec)
        logger.info("[DEVICE] Home Assistant tools: REGISTERED")
    register_browser_tools(tool_registry)
    logger.info("[VEYRA] Tool registry: READY (%d tools)", len(tool_registry.list()))
    async with SessionLocal() as session:
        # Per-integration/per-device failures (an expired credential, an
        # unreachable device) are already handled individually inside
        # these two calls — one integration/device being unavailable at
        # boot never prevents the Local API itself from starting.
        await integration_registry.reconnect_all_on_startup(session, tool_registry)
        await device_pairing_service.rebuild_permission_cache_on_startup(session)
    init_orchestrator(tool_registry, settings)
    init_voice_manager()
    # Real, optional hardware pipeline (wake-word/STT/TTS/audio I/O) —
    # never fatal to startup if nothing is configured or hardware is
    # absent; see build_and_start_voice_pipeline's own docstring.
    await build_and_start_voice_pipeline(settings)

    # Subsystem activation (docs/subsystem-activation/SUBSYSTEM-ACTIVATION-
    # REPORT.md): structured, per-subsystem startup logging using the same
    # real checks GET /system reports — never a bare "started" claim.
    async with SessionLocal() as session:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "computer_control.enabled")
        )
        row = result.scalars().first()
        computer_control_enabled = bool(row.value) if row is not None else False

    logger.info("[AI] Initializing")
    ai_health = compute_ai_status(settings)
    logger.info("[AI] %s — %s", ai_health.status, ai_health.reason)

    logger.info("[VOICE] Initializing")
    voice_health = compute_voice_status(settings)
    logger.info("[VOICE] %s — %s", voice_health.status, voice_health.reason)

    logger.info("[VISION] Initializing")
    vision_health = compute_vision_status(settings)
    logger.info("[VISION] %s — %s", vision_health.status, vision_health.reason)

    logger.info("[COMPUTER] Initializing")
    computer_control_health = compute_computer_control_status(
        enabled_flag=computer_control_enabled, capabilities=detect_capabilities()
    )
    logger.info(
        "[COMPUTER] %s — %s", computer_control_health.status, computer_control_health.reason
    )

    logger.info("[DEVICE] Gateway initialized")
    iot_health = compute_iot_status(device_pairing_service)
    logger.info("[DEVICE] %s — %s", iot_health.status, iot_health.reason)

    mark_ready()
    logger.info("[VEYRA] Local API: READY")
    asyncio.create_task(_startup_ai_health_check())
    logger.info("[VEYRA] Listening: %s:%s", settings.host, settings.port)
    yield

    # Phase 10 P1 (docs/phase-10/PRODUCTION-AUDIT.md — "shutdown does one
    # thing"): a /ready check racing shutdown must see the truth, every
    # open WebSocket gets a real close instead of just dying with the
    # process, the Chromium process Phase 8 launches must never outlive
    # this one, and the DB engine's own connections are released
    # explicitly rather than left for the OS to clean up.
    mark_not_ready()
    logger.info("[VEYRA] Shutting down")
    await stop_voice_pipeline()
    await close_all_websockets()
    await browser_manager.close_all()
    await engine.dispose()
    logger.info("[VEYRA] Local API: STOPPED")
    for handler in logging.getLogger().handlers:
        handler.flush()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=BACKEND_VERSION,
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
    app.include_router(browser_api.router)

    return app


app = create_app()
