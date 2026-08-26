"""Shared default SystemSetting values. Single source of truth used by both
the Alembic seed migration (database/migrations/versions/..._seed_...py)
and the test suite, so they can never drift apart.
See docs/security/05-DATA-PROTECTION.md §3.
"""

from __future__ import annotations

DEFAULT_SETTINGS: dict[str, object] = {
    "microphone.enabled": False,
    "screen_observation.enabled": False,
    "external_devices.enabled": False,
    "remote_access.enabled": False,
    "ai.mode": None,
    "ai.configured": False,
    "voice.configured": False,
    "vision.configured": False,
    "computer_control.enabled": False,
    "security.active": True,
}
