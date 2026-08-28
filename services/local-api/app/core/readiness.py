"""Process-lifetime readiness state — backs `GET /ready` (Part 5: "GET
/health GET /ready GET /system", each a genuinely different concept:
`/health` is pure liveness (the process is alive enough to answer HTTP at
all, checked before this module's flag is even set); `/ready` is "has
startup actually finished" (migrations applied, tools registered — the
same real work `app.main`'s lifespan already does, this just exposes
whether it's done); `/system` remains the full, per-subsystem status
report. Mirrors the same process-global-singleton pattern every other
piece of app-lifetime state in this codebase already uses (tool_registry,
device_pairing_service, credential_manager).
"""

from __future__ import annotations

import time

_ready = False
_started_at: float | None = None


def mark_started() -> None:
    """Called once, first, at the very start of the lifespan — before
    anything that could fail. Powers `/system`'s `uptime_seconds`."""
    global _started_at
    _started_at = time.monotonic()


def mark_ready() -> None:
    """Called once, last, after every startup step in `app.main`'s
    lifespan has genuinely succeeded — never earlier, and never on a
    partial/degraded startup (a failed startup already raises and stops
    the process before this would run)."""
    global _ready
    _ready = True


def mark_not_ready() -> None:
    """Called on shutdown, so a `/ready` check racing the very end of
    process teardown reports the truth instead of a stale `True`."""
    global _ready
    _ready = False


def is_ready() -> bool:
    return _ready


def uptime_seconds() -> float | None:
    if _started_at is None:
        return None
    return time.monotonic() - _started_at
