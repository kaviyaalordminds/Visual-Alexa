"""Real, per-subsystem status computation for AI/Voice/Vision/Computer
Control/IoT. docs/subsystem-activation/SUBSYSTEM-ACTIVATION-REPORT.md.

The absolute rule this whole module exists to satisfy: never report a
subsystem as CONNECTED merely because a config file exists, a process
started, a Python module imported, or an API endpoint exists. Every
function here either performs a real, cheap, synchronous check (platform
detection, binary-on-PATH detection, a permission-cache lookup) or reads
back the result of a real check that was already performed elsewhere (the
AI connectivity cache, updated only by an actual network probe in
`app/services/agent/providers.py`, never guessed at here).

`ai`/`voice`/`vision`/`computer_control`/`iot` all use exactly the same
`ComponentStatus` literal `/system` (`app/api/system.py`) already returns
— this module has no separate status vocabulary of its own.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from computer_control.core.capabilities import PlatformCapabilities

from app.core.config import Settings
from app.services.agent.llm_provider import LLMResult
from app.services.browser.manager import BrowserManager
from app.services.device_pairing import DevicePairingService

# The single source of truth for every status value any component in
# `GET /system`'s response can take — app/api/system.py imports this
# rather than defining its own, so there is exactly one status vocabulary
# in the whole app, never two that could drift apart.
ComponentStatus = Literal[
    "CONNECTED",
    "NOT CONFIGURED",
    "NOT ENABLED",
    "NOT CONNECTED",
    "ACTIVE",
    "ERROR",
    "DEGRADED",
    "DISABLED",
]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SubsystemHealth:
    status: ComponentStatus
    reason: str


# --- AI -----------------------------------------------------------------
#
# `/system` never makes a network call on its own (a passive 5s poll is
# not the place for a billable, possibly-slow inference or even a
# reachability probe against a real provider — see providers.py's own
# docstring). Instead it reads back the result of the last explicit
# connectivity check, performed only when the `system.ai_health_check`
# tool is actually invoked (a real user/UI action, matching the brief's
# own "AI HEALTH CHECK" vs "AI TEST" distinction). A configured-but-
# never-tested provider is reported as DEGRADED, not a false CONNECTED.


@dataclass(frozen=True)
class _AICheckCacheEntry:
    checked_at: datetime
    available: bool
    reason: str | None


_ai_check_cache: _AICheckCacheEntry | None = None


def record_ai_check_result(result: LLMResult) -> None:
    """Called only by the `system.ai_health_check` tool executor after a
    real connectivity probe. Never called from `/system` itself."""
    global _ai_check_cache
    _ai_check_cache = _AICheckCacheEntry(
        checked_at=_now(), available=result.available, reason=result.reason
    )


def reset_ai_check_cache() -> None:
    """Test-isolation helper — this cache is a process-global singleton
    like every other registry here (device_pairing's permission cache,
    tool_registry), so one test's result must not leak into the next."""
    global _ai_check_cache
    _ai_check_cache = None


def compute_ai_status(settings: Settings) -> SubsystemHealth:
    missing = [
        label
        for label, value in (
            ("provider", settings.ai_provider),
            ("model", settings.ai_model),
            ("API key", settings.ai_api_key),
            ("base URL", settings.ai_base_url),
        )
        if not value
    ]
    if missing:
        return SubsystemHealth(
            status="NOT CONFIGURED",
            reason=f"No AI provider configured (missing: {', '.join(missing)}).",
        )
    if _ai_check_cache is None:
        return SubsystemHealth(
            status="DEGRADED",
            reason=(
                f"AI provider '{settings.ai_provider}' is configured but has not been "
                "tested yet — invoke the system.ai_health_check tool to verify connectivity."
            ),
        )
    if _ai_check_cache.available:
        return SubsystemHealth(
            status="CONNECTED",
            reason=(
                f"AI provider '{settings.ai_provider}' verified reachable "
                f"(last checked {_ai_check_cache.checked_at.isoformat()})."
            ),
        )
    return SubsystemHealth(
        status="ERROR",
        reason=_ai_check_cache.reason or "Last connectivity check failed for an unknown reason.",
    )


# --- Voice ----------------------------------------------------------------


def compute_voice_status(settings: Settings) -> SubsystemHealth:
    declared = [
        p for p in (settings.stt_provider, settings.tts_provider, settings.wake_word_provider) if p
    ]
    if not declared:
        return SubsystemHealth(
            status="NOT CONFIGURED", reason="No STT/TTS/wake-word provider configured."
        )
    # Real and honest: services/voice/voice/providers/base.py ships only
    # NotConfigured* implementations — no real audio pipeline exists in
    # this build regardless of what an operator names here. Declaring
    # intent still produces a more useful reason than a bare default.
    return SubsystemHealth(
        status="NOT CONFIGURED",
        reason=(
            f"Configured for provider(s) {', '.join(declared)}, but this build has no real "
            "audio/STT/TTS implementation wired in yet — voice remains unavailable "
            "regardless of this setting until a real provider adapter is added."
        ),
    )


# --- Vision -----------------------------------------------------------------


def _ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _screen_capture_available() -> bool:
    # mss is genuinely cross-platform, but capturing anything on Linux/
    # macOS needs an active display server; Windows never does.
    return sys.platform == "win32" or bool(os.environ.get("DISPLAY"))


def compute_vision_status(settings: Settings) -> SubsystemHealth:
    ocr_ok = _ocr_available()
    capture_ok = _screen_capture_available()
    capability_summary = (
        f"OCR {'available' if ocr_ok else 'unavailable'}, "
        f"screen capture {'available' if capture_ok else 'unavailable'}"
    )
    if settings.vision_provider:
        # Declared intent to use a real vision *model* — Phase 3 ships
        # only NotConfiguredVisionProvider, so no real model exists yet
        # regardless of this setting.
        return SubsystemHealth(
            status="DEGRADED" if (ocr_ok or capture_ok) else "NOT CONFIGURED",
            reason=(
                f"Configured for vision model provider '{settings.vision_provider}', but "
                f"this build has no real vision-model implementation wired in yet — "
                f"{capability_summary}."
            ),
        )
    if ocr_ok or capture_ok:
        return SubsystemHealth(
            status="DEGRADED",
            reason=(
                f"No vision model provider configured — {capability_summary}. "
                "Basic screen reading (OCR/capture) works; AI-driven scene "
                "understanding does not."
            ),
        )
    return SubsystemHealth(
        status="NOT CONFIGURED",
        reason=f"No vision provider configured; {capability_summary}.",
    )


# --- Computer Control ---------------------------------------------------


def compute_computer_control_status(
    *, enabled_flag: bool, capabilities: PlatformCapabilities
) -> SubsystemHealth:
    if not enabled_flag:
        return SubsystemHealth(
            status="NOT ENABLED", reason="Computer control permission has not been enabled."
        )
    if not capabilities.is_windows:
        return SubsystemHealth(
            status="DISABLED",
            reason=(
                "Computer control permission is enabled, but Windows UI Automation "
                f"backends are unavailable on this platform ({capabilities.platform!r}) — "
                "Computer Control requires Windows."
            ),
        )
    return SubsystemHealth(
        status="CONNECTED",
        reason="Computer control permission enabled; Windows automation backends available.",
    )


# --- Browser --------------------------------------------------------------
#
# PHASE_12_AUDIT.md §3 — `browser` had no field in `/system` at all despite
# a real Playwright engine existing since Phase 8. Like the AI health check
# above, this deliberately never launches a browser on a passive `/system`
# poll (that would be slow and side-effecting for every status check) —
# it reports CONNECTED only when a real session is already open, and
# otherwise distinguishes "the engine is installed but idle" from "the
# engine isn't even installed," both honest, neither a guess.


def compute_browser_status(browser_manager: BrowserManager) -> SubsystemHealth:
    open_sessions = browser_manager.registry.list()
    if open_sessions:
        return SubsystemHealth(
            status="CONNECTED",
            reason=f"{len(open_sessions)} browser session(s) currently open.",
        )
    if importlib.util.find_spec("playwright") is not None:
        return SubsystemHealth(
            status="NOT CONNECTED",
            reason=(
                "No browser session is open yet — this is the correct default. "
                "Call browser.launch to start one."
            ),
        )
    return SubsystemHealth(
        status="NOT CONFIGURED",
        reason="The playwright package is not installed — browser automation is unavailable.",
    )


# --- IoT ------------------------------------------------------------------


def compute_iot_status(device_pairing_service: DevicePairingService) -> SubsystemHealth:
    if device_pairing_service.has_any_active_permission():
        return SubsystemHealth(
            status="CONNECTED",
            reason="At least one paired device has an active, authorized permission.",
        )
    return SubsystemHealth(
        status="NOT CONNECTED",
        reason=(
            "No IoT device is paired and authorized yet — this is the correct default. "
            "Pair a device (PAIR -> IDENTIFY -> AUTHENTICATE -> AUTHORIZE -> "
            "REGISTER CAPABILITIES -> grant a permission) to enable control."
        ),
    )
