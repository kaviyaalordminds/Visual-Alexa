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

# Phase 2: an isolated filesystem sandbox, never a developer's real
# Documents/Downloads and never the container's actual $HOME (which is
# '/root' in this environment — itself a protected path, see
# app/services/filesystem_config.py). docs/phase-2/FILESYSTEM-CONTROL.md.
_TMP_FS_ROOT = tempfile.mkdtemp(prefix="veyra-fs-tests-")
os.environ["VEYRA_FILESYSTEM_ALLOWED_ROOTS"] = json.dumps([_TMP_FS_ROOT])

from app.core.config import get_settings
from app.db.base import Base
from app.db.seed_defaults import DEFAULT_SETTINGS
from app.db.session import SessionLocal, engine
from app.main import app as fastapi_app
from app.models.application import Application
from app.models.setting import SystemSetting
from app.services.application_registry import load_application_registry
from app.services.bootstrap import register_default_tools
from app.services.computer_control import register_computer_control_tools
from app.services.tool_registry import tool_registry
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
    register_computer_control_tools(tool_registry, settings, application_registry)
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
    return {"application": application, "window": window, "ui_automation": ui_automation}


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
