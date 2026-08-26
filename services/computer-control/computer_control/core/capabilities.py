"""Platform capability detection. docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2:
Phase 2's Windows-specific capabilities are only real on Windows; this
module is the single place that decides, at process startup, which
backend (real Windows vs. platform-unsupported) a tool executor uses.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformCapabilities:
    platform: str
    is_windows: bool
    supports_application_control: bool
    supports_window_management: bool
    supports_ui_automation: bool
    supports_keyboard_mouse: bool
    # process listing (psutil) and screen capture (mss) are genuinely
    # cross-platform — see docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §4.
    supports_process_listing: bool
    supports_screen_capture: bool


def detect_capabilities() -> PlatformCapabilities:
    is_windows = sys.platform == "win32"
    return PlatformCapabilities(
        platform=sys.platform,
        is_windows=is_windows,
        supports_application_control=is_windows,
        supports_window_management=is_windows,
        supports_ui_automation=is_windows,
        supports_keyboard_mouse=is_windows,
        supports_process_listing=True,
        supports_screen_capture=True,
    )
