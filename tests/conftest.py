"""Root pytest fixtures for the whole monorepo test suite (product brief
§30). Points the Local API at a fresh temp SQLite database per test so
tests never touch a developer's real veyra.db, and resets schema + seed
data between tests for isolation.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest
import pytest_asyncio

_TMP_DB_FD, _TMP_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_TMP_DB_FD)
os.environ["VEYRA_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB_PATH}"
os.environ.setdefault("VEYRA_SECRET_KEY", "test-only-secret")

# Phase 7 — an isolated credentials store file, never a developer's real
# one, reset every test alongside the database (see _reset_state below).
_TMP_CREDENTIALS_FD, _TMP_CREDENTIALS_PATH = tempfile.mkstemp(suffix=".enc.json")
os.close(_TMP_CREDENTIALS_FD)
os.unlink(_TMP_CREDENTIALS_PATH)  # FileCredentialStore creates it on first write
os.environ["VEYRA_CREDENTIALS_STORE_PATH"] = _TMP_CREDENTIALS_PATH

# Phase 2: an isolated filesystem sandbox, never a developer's real
# Documents/Downloads and never the container's actual $HOME (which is
# '/root' in this environment — itself a protected path, see
# app/services/filesystem_config.py). docs/phase-2/FILESYSTEM-CONTROL.md.
_TMP_FS_ROOT = tempfile.mkdtemp(prefix="veyra-fs-tests-")
os.environ["VEYRA_FILESYSTEM_ALLOWED_ROOTS"] = json.dumps([_TMP_FS_ROOT])

# Phase 8 — an isolated downloads dir, never a developer's real one.
_TMP_BROWSER_DOWNLOADS_DIR = tempfile.mkdtemp(prefix="veyra-browser-downloads-")
os.environ["VEYRA_BROWSER_DOWNLOADS_DIR"] = _TMP_BROWSER_DOWNLOADS_DIR

from app.api.system import reset_last_status_snapshot
from app.core.config import get_settings
from app.db.base import Base
from app.db.seed_defaults import DEFAULT_SETTINGS
from app.db.session import SessionLocal, engine
from app.main import app as fastapi_app
from app.models.application import Application
from app.models.setting import SystemSetting
from app.services.agent.register import init_orchestrator
from app.services.application_registry import load_application_registry
from app.services.bootstrap import register_default_tools
from app.services.browser.manager import browser_manager
from app.services.browser.observation import observation_service
from app.services.browser.register import register_browser_tools
from app.services.browser.testing import FakeBrowserAdapter
from app.services.computer_control import register_computer_control_tools
from app.services.computer_control.backends import build_backend_bundle
from app.services.credential_manager import credential_manager
from app.services.device_pairing import device_pairing_service
from app.services.integration_registry import integration_registry
from app.services.mock_iot import build_mock_iot_tools, reset_mock_ac_state
from app.services.reference_integration import build_reference_integration_bundle
from app.services.subsystem_diagnostics_tools import register_subsystem_diagnostic_tools
from app.services.subsystem_health import reset_voice_provider_status
from app.services.tool_execution import reset_idempotency_cache
from app.services.tool_registry import tool_registry
from app.services.vision import register_vision_tools
from app.services.voice.register import init_voice_manager
from veyra_contracts import RiskLevel

get_settings.cache_clear()

# A real, safe, cross-platform executable stands in for Notepad/Calculator
# in this Linux test environment — see
# docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2. Application-tool tests
# on this host are always PLATFORM_NOT_SUPPORTED regardless (no
# ApplicationBackend exists outside Windows), so this entry exists mainly
# to exercise computer_control.registry.ApplicationRegistry's own
# resolution logic for real (see tests/unit/test_application_registry.py).
_TEST_APP_IDENTIFIER = "python_test_app"


@pytest_asyncio.fixture(autouse=True)
async def _reset_state(request):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Fresh credentials store per test, matching the fresh DB above — a
    # credentials_ref from a previous test's (now-dropped) Integration/
    # Device row must never resolve to a leftover secret.
    if os.path.exists(_TMP_CREDENTIALS_PATH):
        os.unlink(_TMP_CREDENTIALS_PATH)

    # tool_registry is a process-global singleton (like every other
    # registry here), so a previous test's integration_registry.connect()
    # can leave an integration-owned tool registered after its Integration
    # row has already been dropped above — unregister every one of them
    # before re-registering the reference integration's *definition*
    # (not connecting it; each test starts CONNECT_REQUIRED, same as a
    # fresh process).
    for definition in tool_registry.list():
        if definition.integration_id is not None:
            tool_registry.unregister(definition.id)
    integration_registry.register_definition(build_reference_integration_bundle(credential_manager))

    # Same process-global-singleton reasoning for the mock IoT device's
    # runtime state — a grant or a commanded power/temperature value from
    # a previous test must not leak into this one.
    device_pairing_service.reset_permission_cache()
    reset_mock_ac_state()
    reset_idempotency_cache()
    reset_last_status_snapshot()
    reset_voice_provider_status()
    for mock_definition, mock_executor in build_mock_iot_tools(device_pairing_service):
        tool_registry.register(mock_definition, mock_executor)

    # Phase 8 — a real Chromium launch from a previous test must never
    # leak into this one; the fast default test double is
    # `FakeBrowserAdapter`, matching the existing bundle/fakes precedent
    # for computer_control/vision. Individual real-Playwright tests
    # override `browser_manager.set_adapter_factory(...)` themselves
    # (see tests/integration/test_browser_real_playwright.py) — this
    # fixture always resets it back to the fake for every other test.
    await browser_manager.close_all()
    browser_manager.set_adapter_factory(FakeBrowserAdapter)
    observation_service.cache.clear()
    register_browser_tools(tool_registry)

    # Real seeded defaults everywhere (docs/security/05-DATA-PROTECTION.md
    # §3 — off by default) EXCEPT computer_control.enabled, which almost
    # every Phase 2 test needs reachable to exercise anything at all; the
    # handful of tests that specifically verify the real, unmodified
    # default opt out with @pytest.mark.real_computer_control_default.
    # This mirrors, at fixture granularity, the same "explicit opt-in"
    # pattern the screen_observation.enabled gate uses per-test.
    keep_real_default = request.node.get_closest_marker("real_computer_control_default")

    async with SessionLocal() as session:
        for key, value in DEFAULT_SETTINGS.items():
            if key == "computer_control.enabled" and not keep_real_default:
                value = True
            session.add(SystemSetting(key=key, value=value))
        session.add(
            Application(
                name="Python Test App",
                identifier=_TEST_APP_IDENTIFIER,
                aliases=["python", "python3"],
                executable_candidates=["python3"],
                risk_level=RiskLevel.SAFE,
            )
        )
        await session.commit()
        application_registry = await load_application_registry(session)

    settings = get_settings()
    register_default_tools(tool_registry)
    register_subsystem_diagnostic_tools(tool_registry)
    bundle = build_backend_bundle()
    register_computer_control_tools(tool_registry, settings, application_registry, bundle=bundle)
    register_vision_tools(tool_registry, bundle)
    init_orchestrator(tool_registry, settings)
    init_voice_manager()
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


@pytest.fixture
def fs_sandbox() -> str:
    """The same isolated root the FilesystemEngine is configured with —
    see VEYRA_FILESYSTEM_ALLOWED_ROOTS above."""
    return _TMP_FS_ROOT


@pytest.fixture
def fake_computer_control():
    """Re-registers every Phase 2 tool against
    computer_control.testing's fake backends instead of the real,
    platform-gated ones — so orchestration logic (Policy Engine,
    verification, error mapping) is exercised deterministically on any
    host. See docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2. Returns the
    fakes so a test can seed windows/elements/processes before invoking a
    tool through the API.
    """
    from app.services.computer_control.backends import BackendBundle
    from computer_control.core.capabilities import PlatformCapabilities
    from computer_control.processes import PsutilProcessBackend
    from computer_control.screen import MssScreenBackend
    from computer_control.testing import (
        FakeApplicationBackend,
        FakeUIAutomationBackend,
        FakeWindowBackend,
    )

    application = FakeApplicationBackend()
    window = FakeWindowBackend()
    ui_automation = FakeUIAutomationBackend()

    class _FakeKeyboard:
        async def type_text(self, target, text):
            return True

        async def press(self, target, key):
            return True

        async def hotkey(self, target, keys):
            return True

    class _FakeMouse:
        async def move(self, selector):
            return True

        async def click(self, selector):
            return True

        async def double_click(self, selector):
            return True

        async def right_click(self, selector):
            return True

        async def scroll(self, selector, amount):
            return True

    bundle = BackendBundle(
        capabilities=PlatformCapabilities(
            platform="fake",
            is_windows=True,
            supports_application_control=True,
            supports_window_management=True,
            supports_ui_automation=True,
            supports_keyboard_mouse=True,
            supports_process_listing=True,
            supports_screen_capture=True,
        ),
        application=application,
        window=window,
        ui_automation=ui_automation,
        keyboard=_FakeKeyboard(),
        mouse=_FakeMouse(),
        process=PsutilProcessBackend(),
        screen=MssScreenBackend(window_backend=window),
    )

    settings = get_settings()
    register_computer_control_tools(tool_registry, settings, _fake_app_registry(), bundle=bundle)

    from vision.testing import FakeVisionProvider

    vision_provider = FakeVisionProvider()
    register_vision_tools(tool_registry, bundle, vision_provider=vision_provider)
    return {
        "application": application,
        "window": window,
        "ui_automation": ui_automation,
        "vision_provider": vision_provider,
    }


def _fake_app_registry():
    from computer_control.registry import ApplicationRegistry, ApplicationRegistryEntry

    return ApplicationRegistry(
        [
            ApplicationRegistryEntry(
                identifier="fake_app",
                name="Fake App",
                aliases=("fakeapp",),
                executable_candidates=("python3",),
                risk_level=RiskLevel.SAFE,
            )
        ]
    )
