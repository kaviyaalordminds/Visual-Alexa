"""Constructs the backend bundle this process will use, based on real
platform capability detection — never a config flag a caller could spoof.
docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2.
"""

from __future__ import annotations

from dataclasses import dataclass

from computer_control.core.backends import (
    ApplicationBackend,
    KeyboardBackend,
    MouseBackend,
    UIAutomationBackend,
    WindowBackend,
)
from computer_control.core.capabilities import PlatformCapabilities, detect_capabilities
from computer_control.processes import PsutilProcessBackend
from computer_control.screen import MssScreenBackend


@dataclass
class BackendBundle:
    capabilities: PlatformCapabilities
    application: ApplicationBackend | None
    window: WindowBackend | None
    ui_automation: UIAutomationBackend | None
    keyboard: KeyboardBackend | None
    mouse: MouseBackend | None
    process: PsutilProcessBackend
    screen: MssScreenBackend


def build_backend_bundle() -> BackendBundle:
    capabilities = detect_capabilities()
    window: WindowBackend | None = None
    application: ApplicationBackend | None = None
    ui_automation: UIAutomationBackend | None = None
    keyboard: KeyboardBackend | None = None
    mouse: MouseBackend | None = None

    if capabilities.is_windows:
        # Only imported on Windows — see computer_control.windows package
        # docstring. Not executable in this development environment.
        from computer_control.windows.applications import WindowsApplicationBackend
        from computer_control.windows.keyboard import WindowsKeyboardBackend
        from computer_control.windows.mouse import WindowsMouseBackend
        from computer_control.windows.ui_automation import WindowsUIAutomationBackend
        from computer_control.windows.windows_ctl import WindowsWindowBackend

        application = WindowsApplicationBackend()
        window = WindowsWindowBackend()
        ui_automation = WindowsUIAutomationBackend()
        keyboard = WindowsKeyboardBackend()
        mouse = WindowsMouseBackend()

    return BackendBundle(
        capabilities=capabilities,
        application=application,
        window=window,
        ui_automation=ui_automation,
        keyboard=keyboard,
        mouse=mouse,
        process=PsutilProcessBackend(),
        screen=MssScreenBackend(window_backend=window),
    )
