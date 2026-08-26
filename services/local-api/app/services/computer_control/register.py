"""Registers every Phase 2 tool into the existing (Phase 1) ToolRegistry.
Called once at process startup, alongside app.services.bootstrap's
Phase 1 tool registration — see app/main.py.
"""

from __future__ import annotations

from computer_control.filesystem import FilesystemEngine, PathValidator
from computer_control.registry import ApplicationRegistry

from app.core.config import Settings
from app.services.computer_control.application_tools import build_application_tools
from app.services.computer_control.backends import BackendBundle, build_backend_bundle
from app.services.computer_control.filesystem_tools import build_filesystem_tools
from app.services.computer_control.input_tools import build_input_tools
from app.services.computer_control.screen_tools import build_screen_tools
from app.services.computer_control.ui_tools import build_ui_tools
from app.services.computer_control.window_tools import build_window_tools
from app.services.filesystem_config import build_default_policy
from app.services.tool_registry import ToolRegistry


def register_computer_control_tools(
    registry: ToolRegistry,
    settings: Settings,
    application_registry: ApplicationRegistry,
    bundle: BackendBundle | None = None,
) -> None:
    """`bundle` is normally left as None, resolving real platform
    capabilities via `build_backend_bundle()` — the test suite passes a
    bundle built from `computer_control.testing`'s fakes instead, so the
    orchestration logic (Policy Engine integration, verification,
    error mapping) is exercised against deterministic backends rather
    than only ever seeing PLATFORM_NOT_SUPPORTED in this environment. See
    docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2."""
    bundle = bundle or build_backend_bundle()
    filesystem_engine = FilesystemEngine(PathValidator(build_default_policy(settings)))

    all_tools = (
        build_application_tools(bundle, application_registry)
        + build_window_tools(bundle)
        + build_filesystem_tools(filesystem_engine)
        + build_input_tools(bundle)
        + build_screen_tools(bundle)
        + build_ui_tools(bundle)
    )
    for definition, executor in all_tools:
        registry.register(definition, executor)  # type: ignore[arg-type]
